import hashlib
import json
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.base import utc_now
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentSession, AssessmentType
from app.modules.attempts import service as attempt_service
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.attempts.schema import AttemptCreate
from app.modules.evaluation_runs.model import EvaluationRun
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.files.model import FileType
from app.modules.files.service import save_upload
from app.modules.product_v2.comparability import build_comparable_set, trend_fact
from app.modules.product_v2.model import (
    AttentionItem,
    EvidenceRecord,
    MetricRecord,
    Milestone,
    ObservationRecord,
    RecommendationRecord,
    RehabilitationGoal,
    StageReview,
    TherapistDecision,
    TrainingPlanExerciseRule,
    TrainingPlanVersion,
    TrainingSessionSummary,
)
from app.modules.product_v2.schema import (
    AttemptCreateV2,
    DecisionCreate,
    FormalAssessmentCreate,
    GoalCreate,
    StageReviewCreate,
    TrainingPlanDraftCreate,
)
from app.modules.pronunciation.model import PronunciationAnalysisResult, PronunciationSegment
from app.modules.scenario_dialogues.model import DialogueStatus, ScenarioDialogueEvaluation, ScenarioDialogueSession
from app.modules.scenario_dialogues import service as scenario_dialogue_service
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.scoring.service import analyze_attempt
from app.modules.therapist.service import require_therapist_patient_access
from app.modules.training.model import SessionTask, TaskTemplate, TrainingSession, TrainingStatus, TrainingType
from app.modules.users.model import PatientProfile, TherapistPatientAssignment, User, UserRole
from app.modules.users.service import get_patient_profile


METRIC_LABELS = {
    "acceptance_score": "接受度",
    "cadl_score": "CADL 总分",
    "error_count": "错误次数",
    "loudness": "声音响度",
    "script_accuracy": "表达完整度",
    "speech_rate": "言语速率",
    "independence": "独立完成度",
    "pronunciation_accuracy": "发音准确度",
    "pronunciation_fluency": "发音流利度",
    "pronunciation_completion": "发音完成度",
    "phoneme_accuracy": "音素准确度",
    "tone_accuracy": "声调准确度",
    "pronunciation_mismatch_count": "发音匹配问题",
    "wab_reliability": "WAB 可靠度",
    "wab_fluency": "WAB 流利性",
    "wab_grammar": "WAB 语法",
    "wab_information": "WAB 信息量",
    "wab_repetition_intelligibility": "WAB 复述可懂度",
    "wab_word_order": "WAB 语序",
}
TRAINING_METRICS = {
    "error_count",
    "loudness",
    "script_accuracy",
    "speech_rate",
    "independence",
    "pronunciation_accuracy",
    "pronunciation_fluency",
    "pronunciation_completion",
    "phoneme_accuracy",
    "tone_accuracy",
    "pronunciation_mismatch_count",
}
ASSESSMENT_METRICS = set(METRIC_LABELS) - TRAINING_METRICS - {"wab_reliability"}


def pronunciation_metric_values(analysis: PronunciationAnalysisResult, segments: list[PronunciationSegment]):
    """Convert one completed SOE result into canonical, explainable metrics.

    Provider percentages are normalized at the adapter boundary: fluency and
    completion are stored as percentages here, while the raw response remains
    in the pronunciation Evidence payload. These metrics are intentionally
    training facts; they are not WAB/CADL values.
    """
    if analysis.status != "completed":
        return []

    values = []
    if analysis.overall_accuracy is not None:
        values.append(("pronunciation_accuracy", float(analysis.overall_accuracy), "%"))
    if analysis.fluency is not None:
        fluency = float(analysis.fluency)
        values.append(("pronunciation_fluency", round(fluency * 100 if 0 <= fluency <= 1 else fluency, 2), "%"))
    if analysis.completion is not None:
        completion = float(analysis.completion)
        values.append(("pronunciation_completion", round(completion * 100 if 0 <= completion <= 1 else completion, 2), "%"))

    phonemes = [item.accuracy for item in segments if item.level == "phoneme" and item.accuracy is not None]
    if phonemes:
        values.append(("phoneme_accuracy", round(sum(phonemes) / len(phonemes), 2), "%"))

    tone_items = [item for item in segments if item.tone_correct is not None]
    if tone_items:
        values.append(("tone_accuracy", round(sum(bool(item.tone_correct) for item in tone_items) / len(tone_items) * 100, 2), "%"))

    word_items = [item for item in segments if item.level == "word"]
    mismatches = sum(item.match_type != "matched" for item in word_items)
    if word_items:
        values.append(("pronunciation_mismatch_count", float(mismatches), "count/attempt"))
    return values


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _profile_for_patient_user(db: Session, patient_user_id: UUID) -> PatientProfile:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient_user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="患者档案不存在")
    return profile


def _therapist_profile(db: Session, actor: User, patient_user_id: UUID) -> PatientProfile:
    return require_therapist_patient_access(db, actor, patient_user_id)


def _patient_today(profile: PatientProfile) -> date:
    try:
        zone = ZoneInfo(profile.timezone or "Asia/Shanghai")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Shanghai")
    return datetime.now(timezone.utc).astimezone(zone).date()


def _active_goal(db: Session, profile_id: UUID):
    return db.scalar(
        select(RehabilitationGoal).where(
            RehabilitationGoal.patient_profile_id == profile_id,
            RehabilitationGoal.status == "active",
            RehabilitationGoal.is_primary.is_(True),
        )
    )


def _active_plan(db: Session, profile_id: UUID):
    return db.scalar(
        select(TrainingPlanVersion)
        .options(selectinload(TrainingPlanVersion.exercise_rules).selectinload(TrainingPlanExerciseRule.task_template))
        .where(TrainingPlanVersion.patient_profile_id == profile_id, TrainingPlanVersion.status == "active")
    )


def goal_dict(goal: RehabilitationGoal | None):
    if not goal:
        return None
    return {
        "id": str(goal.id),
        "category": goal.category,
        "description": goal.description,
        "status": goal.status,
        "is_primary": goal.is_primary,
        "effective_from": goal.effective_from.isoformat(),
        "effective_to": goal.effective_to.isoformat() if goal.effective_to else None,
    }


def plan_dict(plan: TrainingPlanVersion | None, include_rules: bool = True):
    if not plan:
        return None
    result = {
        "id": str(plan.id),
        "patient_profile_id": str(plan.patient_profile_id),
        "rehabilitation_goal_id": str(plan.rehabilitation_goal_id),
        "version_number": plan.version_number,
        "status": plan.status,
        "stage_focus": plan.stage_focus,
        "strategy": plan.strategy_snapshot,
        "effective_from": plan.effective_from.isoformat() if plan.effective_from else None,
        "effective_to": plan.effective_to.isoformat() if plan.effective_to else None,
        "published_at": plan.published_at.isoformat() if plan.published_at else None,
        "supersedes_id": str(plan.supersedes_id) if plan.supersedes_id else None,
    }
    if include_rules:
        result["exercise_rules"] = [
            {
                "id": str(rule.id),
                "task_template_id": str(rule.task_template_id),
                "exercise_type": rule.exercise_type,
                "order_index": rule.order_index,
                "target_repetitions": rule.target_repetitions,
                "difficulty": rule.difficulty,
                "max_information_units": rule.max_information_units,
                "prompt_policy": rule.prompt_policy,
                "scene_scope": rule.scene_scope,
                "title": rule.task_template.title if rule.task_template else None,
            }
            for rule in plan.exercise_rules
        ]
    return result


def create_goal(db: Session, actor: User, patient_user_id: UUID, payload: GoalCreate):
    profile = _therapist_profile(db, actor, patient_user_id)
    if payload.is_primary:
        current = _active_goal(db, profile.id)
        if current:
            current.status = "ended"
            current.effective_to = payload.effective_from or _patient_today(profile)
    goal = RehabilitationGoal(
        patient_profile_id=profile.id,
        created_by_user_id=actor.id,
        category=payload.category.strip(),
        description=payload.description.strip(),
        status="active",
        is_primary=payload.is_primary,
        effective_from=payload.effective_from or _patient_today(profile),
        effective_to=payload.effective_to,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal_dict(goal)


def create_plan_draft(db: Session, actor: User, patient_user_id: UUID, payload: TrainingPlanDraftCreate):
    profile = _therapist_profile(db, actor, patient_user_id)
    goal = db.get(RehabilitationGoal, payload.rehabilitation_goal_id)
    if not goal or goal.patient_profile_id != profile.id or goal.status != "active":
        raise HTTPException(status_code=409, detail="训练方案必须关联该患者的有效康复目标")
    templates = {
        item.id: item
        for item in db.scalars(select(TaskTemplate).where(TaskTemplate.id.in_([rule.task_template_id for rule in payload.exercise_rules])))
    }
    if len(templates) != len({rule.task_template_id for rule in payload.exercise_rules}):
        raise HTTPException(status_code=422, detail="训练方案包含不存在的练习模板")
    for rule in payload.exercise_rules:
        if _enum_value(templates[rule.task_template_id].task_type) != rule.exercise_type:
            raise HTTPException(status_code=422, detail="练习类型与模板不一致")
    version = (db.scalar(select(func.max(TrainingPlanVersion.version_number)).where(TrainingPlanVersion.patient_profile_id == profile.id)) or 0) + 1
    plan = TrainingPlanVersion(
        patient_profile_id=profile.id,
        rehabilitation_goal_id=goal.id,
        version_number=version,
        status="draft",
        stage_focus=payload.stage_focus.strip(),
        strategy_snapshot={
            "frequency": payload.frequency,
            "duration": payload.duration_minutes,
            "forms": payload.forms,
            "scene_scope": payload.scene_scope,
            "difficulty": payload.difficulty,
            "max_information_units": payload.max_information_units,
            "prompt_policy": payload.prompt_policy,
        },
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        supersedes_id=payload.supersedes_id,
    )
    db.add(plan)
    db.flush()
    for rule in payload.exercise_rules:
        db.add(
            TrainingPlanExerciseRule(
                training_plan_version_id=plan.id,
                task_template_id=rule.task_template_id,
                exercise_type=rule.exercise_type,
                order_index=rule.order_index,
                target_repetitions=rule.target_repetitions,
                difficulty=rule.difficulty,
                max_information_units=rule.max_information_units,
                prompt_policy=rule.prompt_policy,
                scene_scope=rule.scene_scope,
            )
        )
    db.commit()
    return plan_dict(
        db.scalar(
            select(TrainingPlanVersion)
            .options(selectinload(TrainingPlanVersion.exercise_rules).selectinload(TrainingPlanExerciseRule.task_template))
            .where(TrainingPlanVersion.id == plan.id)
        )
    )


def publish_plan(db: Session, actor: User, patient_user_id: UUID, plan_id: UUID):
    profile = _therapist_profile(db, actor, patient_user_id)
    plan = db.scalar(select(TrainingPlanVersion).where(TrainingPlanVersion.id == plan_id).with_for_update())
    if not plan or plan.patient_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="训练方案不存在")
    if plan.status != "draft":
        raise HTTPException(status_code=409, detail="只有草稿方案可以发布；已发布版本不可原地编辑")
    if not db.scalar(select(func.count(TrainingPlanExerciseRule.id)).where(TrainingPlanExerciseRule.training_plan_version_id == plan.id)):
        raise HTTPException(status_code=409, detail="训练方案至少需要一个练习")
    current = db.scalar(
        select(TrainingPlanVersion)
        .where(TrainingPlanVersion.patient_profile_id == profile.id, TrainingPlanVersion.status == "active")
        .with_for_update()
    )
    now = utc_now()
    today = _patient_today(profile)
    if current:
        current.status = "superseded"
        current.effective_to = today
        plan.supersedes_id = current.id
        # Release the partial unique slot before activating the replacement.
        # This remains in the same transaction, so a later failure restores the
        # previous active plan rather than leaving the patient without one.
        db.flush()
    plan.status = "active"
    plan.published_by_user_id = actor.id
    plan.published_at = now
    plan.effective_from = plan.effective_from or today
    db.commit()
    return plan_dict(
        db.scalar(
            select(TrainingPlanVersion)
            .options(selectinload(TrainingPlanVersion.exercise_rules).selectinload(TrainingPlanExerciseRule.task_template))
            .where(TrainingPlanVersion.id == plan.id)
        )
    )


def list_plans(db: Session, actor: User, patient_user_id: UUID):
    profile = _therapist_profile(db, actor, patient_user_id)
    rows = db.scalars(
        select(TrainingPlanVersion)
        .options(selectinload(TrainingPlanVersion.exercise_rules).selectinload(TrainingPlanExerciseRule.task_template))
        .where(TrainingPlanVersion.patient_profile_id == profile.id)
        .order_by(TrainingPlanVersion.version_number.desc())
    )
    return [plan_dict(row) for row in rows]


def _session_owned(db: Session, user: User, session_id: UUID) -> TrainingSession:
    profile = get_patient_profile(db, user)
    session = db.scalar(select(TrainingSession).options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template)).where(TrainingSession.id == session_id))
    if not session or session.patient_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="训练记录不存在")
    return session


def start_or_resume(db: Session, user: User, session_kind: str = "formal", requested_plan_id: UUID | None = None):
    profile = get_patient_profile(db, user)
    today = _patient_today(profile)
    if session_kind == "formal":
        resumable = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.local_session_date == today,
                TrainingSession.session_kind == "formal",
                TrainingSession.v2_status.in_(["in_progress", "paused"]),
            )
            .order_by(TrainingSession.started_at.desc())
        )
        if resumable:
            return session_dict(db, resumable)
    plan = _active_plan(db, profile.id)
    if requested_plan_id:
        requested = db.get(TrainingPlanVersion, requested_plan_id)
        if not requested or requested.patient_profile_id != profile.id or requested.status != "active":
            raise HTTPException(status_code=409, detail="请求的训练方案不是当前有效方案")
        plan = _active_plan(db, profile.id)
    if not plan:
        raise HTTPException(status_code=409, detail="治疗师尚未发布正式训练方案")
    if session_kind == "formal":
        existing = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.formal_training_plan_version_id == plan.id,
                TrainingSession.local_session_date == today,
                TrainingSession.session_kind == "formal",
            )
        )
        if existing:
            return session_dict(db, existing)
    rules = plan.exercise_rules
    if not rules:
        raise HTTPException(status_code=409, detail="当前训练方案没有可执行练习")
    session = TrainingSession(
        patient_profile_id=profile.id,
        agent_id=profile.current_agent_id,
        formal_training_plan_version_id=plan.id,
        session_kind=session_kind,
        v2_status="in_progress",
        local_session_date=today,
        started_at=utc_now(),
        summary_status="pending",
        technical_status="ready",
        training_type=TrainingType.repeat if any(rule.exercise_type == "repeat" for rule in rules) else TrainingType.scenario,
        status=TrainingStatus.in_progress,
    )
    db.add(session)
    db.flush()
    for rule in rules:
        template = rule.task_template
        content = {
            "template_id": str(template.id),
            "title": template.title,
            "scene_prompt": template.scene_prompt,
            "scoring_config": template.scoring_config,
            "tags": template.tags,
        }
        db.add(
            SessionTask(
                training_session_id=session.id,
                task_template_id=template.id,
                order_index=rule.order_index,
                prompt_level=0,
                status=TrainingStatus.in_progress,
                v2_status="planned",
                content_snapshot=content,
                instruction_snapshot=template.instruction,
                target_snapshot=template.target_text,
                exercise_type_snapshot=rule.exercise_type,
                difficulty_snapshot=rule.difficulty,
                max_information_units_snapshot=rule.max_information_units,
                prompt_policy_snapshot=rule.prompt_policy,
                contract_version_snapshot=str((template.scoring_config or {}).get("version", "legacy-template-v1")),
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if session_kind != "formal":
            raise
        concurrent = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.formal_training_plan_version_id == plan.id,
                TrainingSession.local_session_date == today,
                TrainingSession.session_kind == "formal",
            )
        )
        if concurrent:
            return session_dict(db, concurrent)
        raise
    return session_dict(db, _session_owned(db, user, session.id))


def _task_dict(db: Session, task: SessionTask):
    attempts = list(db.scalars(select(Attempt).where(Attempt.session_task_id == task.id).order_by(Attempt.attempt_no)))
    dialogue = db.scalar(select(ScenarioDialogueSession).where(ScenarioDialogueSession.session_task_id == task.id))
    return {
        "id": str(task.id),
        "order_index": task.order_index,
        "status": task.v2_status,
        "exercise_type": task.exercise_type_snapshot or _enum_value(task.task_template.task_type),
        "title": task.content_snapshot.get("title") or task.task_template.title,
        "instruction": task.instruction_snapshot or task.task_template.instruction,
        "target": task.target_snapshot or task.task_template.target_text,
        "difficulty": task.difficulty_snapshot,
        "max_information_units": task.max_information_units_snapshot,
        "prompt_level": task.prompt_level,
        "prompt_policy": task.prompt_policy_snapshot,
        "scenario_dialogue_id": str(dialogue.id) if dialogue else None,
        "attempts": [
            {
                "id": str(item.id),
                "attempt_no": item.attempt_no,
                "prompt_level": item.prompt_level,
                "terminal_state": item.terminal_state,
                "technical_validity": item.technical_validity,
                "measurement_eligibility": item.measurement_eligibility,
                "analysis_status": _enum_value(item.analysis_status),
                "audio_file_id": str(item.audio_file_id) if item.audio_file_id else None,
                "requested_help": item.requested_help,
                "skipped": item.skipped,
            }
            for item in attempts
        ],
    }


def session_dict(db: Session, session: TrainingSession):
    tasks = [_task_dict(db, task) for task in sorted(session.session_tasks, key=lambda item: item.order_index)]
    current = next((item for item in tasks if item["status"] not in {"completed", "skipped", "technical_invalid"}), None)
    return {
        "id": str(session.id),
        "patient_profile_id": str(session.patient_profile_id),
        "plan_version_id": str(session.formal_training_plan_version_id) if session.formal_training_plan_version_id else None,
        "session_kind": session.session_kind,
        "status": session.v2_status,
        "local_session_date": session.local_session_date.isoformat() if session.local_session_date else None,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "paused_at": session.paused_at.isoformat() if session.paused_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "summary_status": session.summary_status,
        "technical_status": session.technical_status,
        "exercises": tasks,
        "current_exercise": current,
        "resume_position": current["order_index"] if current else len(tasks),
    }


def get_patient_session(db: Session, user: User, session_id: UUID):
    session = _session_owned(db, user, session_id)
    _refresh_task_states(db, session)
    db.commit()
    return session_dict(db, _session_owned(db, user, session_id))


def session_command(db: Session, user: User, session_id: UUID, command: str, reason: str | None = None):
    session = _session_owned(db, user, session_id)
    if command == "pause":
        if session.v2_status != "in_progress":
            raise HTTPException(status_code=409, detail="只有进行中的训练可以暂停")
        session.v2_status = "paused"
        session.paused_at = utc_now()
    elif command == "resume":
        if session.v2_status != "paused":
            raise HTTPException(status_code=409, detail="只有已暂停的训练可以继续")
        session.v2_status = "in_progress"
        session.resumed_at = utc_now()
    elif command == "abort":
        if session.v2_status in {"completed", "aborted"}:
            raise HTTPException(status_code=409, detail="训练已经结束")
        session.v2_status = "aborted"
        session.aborted_at = utc_now()
        session.technical_status = reason or "patient_aborted"
    elif command == "complete":
        _refresh_task_states(db, session)
        pending = [task for task in session.session_tasks if task.v2_status not in {"completed", "skipped", "technical_invalid"}]
        if pending:
            raise HTTPException(status_code=409, detail="仍有练习尚未结束")
        session.v2_status = "completed"
        session.status = TrainingStatus.completed
        session.completed_at = utc_now()
        _create_summary(db, session)
        _derive_milestones(db, session)
    else:
        raise HTTPException(status_code=404, detail="未知训练命令")
    db.commit()
    return session_dict(db, _session_owned(db, user, session.id))


def task_command(db: Session, user: User, session_id: UUID, task_id: UUID, command: str):
    session = _session_owned(db, user, session_id)
    task = next((item for item in session.session_tasks if item.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="练习不存在")
    if command == "hint":
        task.prompt_level = min(3, task.prompt_level + 1)
        task.v2_status = "in_progress"
    elif command == "help":
        task.v2_status = "in_progress"
        create_attention(
            db,
            session.patient_profile_id,
            "patient_help_request",
            "explicit_patient_help",
            f"患者在“{task.content_snapshot.get('title', '训练')}”中请求帮助。",
            f"help:{task.id}",
            [{"type": "session_task", "id": str(task.id)}],
            priority="normal",
        )
    elif command == "skip":
        attempt = Attempt(
            session_task_id=task.id,
            attempt_no=(db.scalar(select(func.count(Attempt.id)).where(Attempt.session_task_id == task.id)) or 0) + 1,
            prompt_level=task.prompt_level,
            skipped=True,
            terminal_state="skipped",
            technical_validity="not_applicable",
            measurement_eligibility="not_observed",
            completed_at=utc_now(),
            analysis_status=AnalysisStatus.completed,
        )
        db.add(attempt)
        task.v2_status = "skipped"
        task.status = TrainingStatus.completed
    else:
        raise HTTPException(status_code=404, detail="未知练习命令")
    db.commit()
    return session_dict(db, _session_owned(db, user, session.id))


def create_attempt_v2(db: Session, user: User, payload: AttemptCreateV2):
    attempt = attempt_service.create_attempt(db, user, AttemptCreate(**payload.model_dump()))
    attempt.terminal_state = "pending"
    attempt.technical_validity = "unknown"
    attempt.measurement_eligibility = "pending"
    task = db.get(SessionTask, attempt.session_task_id)
    task.v2_status = "in_progress"
    task.prompt_level = max(task.prompt_level, attempt.prompt_level)
    db.commit()
    db.refresh(attempt)
    return attempt


def upload_attempt_audio(db: Session, user: User, attempt_id: UUID, upload: UploadFile):
    return attempt_service.upload_audio(db, user, attempt_id, upload)


def analyze_attempt_v2(db: Session, user: User, attempt_id: UUID):
    attempt = attempt_service.get_attempt(db, user, attempt_id)
    try:
        feedback = analyze_attempt(db, attempt)
        attempt.terminal_state = "completed"
        attempt.technical_validity = "valid"
        attempt.measurement_eligibility = "eligible"
        attempt.completed_at = utc_now()
        task = db.get(SessionTask, attempt.session_task_id)
        task.v2_status = "completed"
        task.status = TrainingStatus.completed
        db.commit()
        project_attempt(db, attempt.id)
        return {"attempt": _task_dict(db, task)["attempts"][-1], "feedback": feedback.model_dump(mode="json")}
    except HTTPException:
        db.rollback()
        attempt = attempt_service.get_attempt(db, user, attempt_id)
        attempt.terminal_state = "technical_invalid"
        attempt.technical_validity = "invalid"
        attempt.measurement_eligibility = "invalid"
        attempt.completed_at = utc_now()
        task = db.get(SessionTask, attempt.session_task_id)
        task.v2_status = "technical_invalid"
        task.status = TrainingStatus.completed
        db.commit()
        _attention_for_technical_failure(db, attempt)
        raise


def project_attempt(db: Session, attempt_id: UUID):
    attempt = db.get(Attempt, attempt_id)
    task = db.get(SessionTask, attempt.session_task_id) if attempt else None
    session = db.get(TrainingSession, task.training_session_id) if task else None
    if not attempt or not task or not session:
        return
    analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
    provider_version = analysis.provider_version if analysis else None
    provider = (provider_version or "unknown").split(":", 1)[0]
    source_status = "mock" if "mock" in (provider_version or "").lower() else "real"
    evidence = db.scalar(
        select(EvidenceRecord).where(
            EvidenceRecord.source_type == "attempt", EvidenceRecord.source_id == attempt.id, EvidenceRecord.evidence_type == "attempt_bundle"
        )
    )
    if not evidence:
        evidence = EvidenceRecord(
            patient_profile_id=session.patient_profile_id,
            training_session_id=session.id,
            evidence_type="attempt_bundle",
            source_type="attempt",
            source_id=attempt.id,
            source_status=source_status,
            provider=provider,
            provider_version=provider_version,
            quality_status=attempt.audio_quality or "unknown",
            payload={
                "audio_file_id": str(attempt.audio_file_id) if attempt.audio_file_id else None,
                "transcript": analysis.asr_text if analysis else None,
                "task_snapshot": task.content_snapshot,
                "prompt_level": attempt.prompt_level,
            },
            measured_at=attempt.completed_at or attempt.created_at,
        )
        db.add(evidence)
        db.flush()
    rows = db.execute(
        select(AttemptEvaluation, EvaluationMetric)
        .join(EvaluationMetric, EvaluationMetric.id == AttemptEvaluation.metric_id)
        .where(AttemptEvaluation.attempt_id == attempt.id)
    ).all()
    for evaluation, definition in rows:
        eval_source = _enum_value(evaluation.evaluation_source)
        mock = source_status == "mock" or eval_source == EvaluationSource.mock_ai.value
        context = {
            "task_family": task.exercise_type_snapshot or _enum_value(task.task_template.task_type),
            "exercise_contract_version": task.contract_version_snapshot,
            "difficulty": task.difficulty_snapshot,
            "max_information_units": task.max_information_units_snapshot,
            "prompt_policy": task.prompt_policy_snapshot,
            "prompt_level": attempt.prompt_level,
        }
        key_source = {
            "code": definition.name,
            "context": context,
            "algorithm": evaluation.algorithm_version,
            "provider": provider,
            "unit": evaluation.unit or definition.unit,
        }
        comparison_key = hashlib.sha256(json.dumps(key_source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        metric = db.scalar(
            select(MetricRecord).where(
                MetricRecord.source_type == "attempt", MetricRecord.source_id == attempt.id, MetricRecord.code == definition.name
            )
        )
        if not metric:
            db.add(
                MetricRecord(
                    patient_profile_id=session.patient_profile_id,
                    training_session_id=session.id,
                    code=definition.name,
                    value=evaluation.value,
                    status="invalid" if mock else "measured",
                    unit=evaluation.unit or definition.unit,
                    measured_at=evaluation.created_at,
                    measurement_context=context,
                    source_type="attempt",
                    source_id=attempt.id,
                    provider=provider,
                    algorithm=evaluation.algorithm_version,
                    version=evaluation.algorithm_version,
                    quality={"quality_status": evaluation.quality_status, "source_status": "mock" if mock else "real"},
                    evidence_ids=[str(evidence.id)],
                    comparison_key=comparison_key,
                    decision_eligible=bool(evaluation.decision_eligible and not mock),
                )
            )

    # Project Tencent SOE's fine-grained pronunciation result into the v2
    # evidence/metric boundary. The result remains training evidence and is
    # deliberately not eligible for clinical profile decisions until the
    # pronunciation contract has been locally validated.
    pronunciation = db.scalar(
        select(PronunciationAnalysisResult)
        .where(PronunciationAnalysisResult.attempt_id == attempt.id)
        .options(selectinload(PronunciationAnalysisResult.segments))
    )
    if pronunciation:
        pronunciation_real = pronunciation.provider == "tencent_soe" and pronunciation.status == "completed"
        pronunciation_source_status = "real" if pronunciation_real else "unavailable"
        pronunciation_evidence = db.scalar(
            select(EvidenceRecord).where(
                EvidenceRecord.source_type == "attempt",
                EvidenceRecord.source_id == attempt.id,
                EvidenceRecord.evidence_type == "pronunciation_bundle",
            )
        )
        segments = list(pronunciation.segments or [])
        segment_payload = [
            {
                "level": item.level,
                "ordinal": item.ordinal,
                "reference_text": item.reference_text,
                "recognized_text": item.recognized_text,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "accuracy": item.accuracy,
                "fluency": item.fluency,
                "match_type": item.match_type,
                "reference_tone": item.reference_tone,
                "recognized_tone": item.recognized_tone,
                "tone_correct": item.tone_correct,
            }
            for item in segments
        ]
        if not pronunciation_evidence:
            pronunciation_evidence = EvidenceRecord(
                patient_profile_id=session.patient_profile_id,
                training_session_id=session.id,
                evidence_type="pronunciation_bundle",
                source_type="attempt",
                source_id=attempt.id,
                source_status=pronunciation_source_status,
                provider=pronunciation.provider,
                provider_version=pronunciation.provider_version,
                quality_status=pronunciation.status,
                payload={
                    "evaluation_mode": pronunciation.evaluation_mode,
                    "overall_accuracy": pronunciation.overall_accuracy,
                    "fluency": pronunciation.fluency,
                    "completion": pronunciation.completion,
                    "suggested_score": pronunciation.suggested_score,
                    "confidence": pronunciation.confidence,
                    "coverage": pronunciation.coverage,
                    "segments": segment_payload,
                    "raw_provider_output": pronunciation.raw_provider_output,
                    "error_code": pronunciation.error_code,
                    "error_message": pronunciation.error_message,
                },
                measured_at=pronunciation.created_at,
            )
            db.add(pronunciation_evidence)
            db.flush()
        for code, value, unit in pronunciation_metric_values(pronunciation, segments):
            metric_context = {
                "task_family": "repeat",
                "evaluation_mode": pronunciation.evaluation_mode,
                "contract_version": task.contract_version_snapshot,
                "pronunciation_shadow": True,
            }
            comparison_key = hashlib.sha256(
                json.dumps(
                    {
                        "code": code,
                        "provider": pronunciation.provider,
                        "provider_version": pronunciation.provider_version,
                        "evaluation_mode": pronunciation.evaluation_mode,
                        "contract_version": task.contract_version_snapshot,
                        "unit": unit,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            existing = db.scalar(
                select(MetricRecord).where(
                    MetricRecord.source_type == "attempt_pronunciation",
                    MetricRecord.source_id == attempt.id,
                    MetricRecord.code == code,
                )
            )
            if existing:
                continue
            db.add(
                MetricRecord(
                    patient_profile_id=session.patient_profile_id,
                    training_session_id=session.id,
                    code=code,
                    value=value,
                    status="measured",
                    unit=unit,
                    measured_at=pronunciation.created_at,
                    measurement_context=metric_context,
                    source_type="attempt_pronunciation",
                    source_id=attempt.id,
                    provider=pronunciation.provider,
                    algorithm=pronunciation.algorithm_version,
                    version=pronunciation.provider_version,
                    quality={
                        "source_status": pronunciation_source_status,
                        "provider_status": pronunciation.status,
                        "confidence": pronunciation.confidence,
                        "coverage": pronunciation.coverage,
                        "review_status": pronunciation.review_status,
                        "decision_eligible": False,
                    },
                    evidence_ids=[str(pronunciation_evidence.id)],
                    comparison_key=comparison_key,
                    decision_eligible=False,
                )
            )
    db.commit()
    refresh_longitudinal_insights(db, session.patient_profile_id)


def _attention_for_technical_failure(db: Session, attempt: Attempt):
    task = db.get(SessionTask, attempt.session_task_id)
    session = db.get(TrainingSession, task.training_session_id) if task else None
    if not session:
        return
    failures = db.scalar(
        select(func.count(Attempt.id)).where(
            Attempt.session_task_id == task.id,
            Attempt.terminal_state == "technical_invalid",
        )
    ) or 0
    if failures >= 2:
        create_attention(
            db,
            session.patient_profile_id,
            "repeated_ungradable_attempt",
            "repeated_technical_invalid",
            "同一练习连续出现不可评分记录，需要检查录音或设备状态。",
            f"technical-invalid:{task.id}",
            [{"type": "attempt", "id": str(attempt.id)}],
            priority="normal",
        )
        db.commit()


def _refresh_task_states(db: Session, session: TrainingSession):
    for task in session.session_tasks:
        if (task.exercise_type_snapshot or _enum_value(task.task_template.task_type)) == "scenario":
            dialogue = db.scalar(select(ScenarioDialogueSession).where(ScenarioDialogueSession.session_task_id == task.id))
            if dialogue and _enum_value(dialogue.status) in {"completed", "aborted"}:
                task.v2_status = "completed" if _enum_value(dialogue.status) == "completed" else "technical_invalid"
                task.status = TrainingStatus.completed
                if _enum_value(dialogue.status) == "completed":
                    project_scenario(db, dialogue.id)


def project_scenario(db: Session, dialogue_id: UUID):
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    evaluation = (
        scenario_dialogue_service.ensure_evaluation(db, dialogue_id)
        if dialogue and _enum_value(dialogue.status) in {"completed", "aborted"}
        else None
    )
    task = db.get(SessionTask, dialogue.session_task_id) if dialogue else None
    session = db.get(TrainingSession, task.training_session_id) if task else None
    if not dialogue or not evaluation or not task or not session:
        return
    source_status = "mock" if any("mock" in str(value).lower() for value in (dialogue.contract_snapshot or {}).values()) else "real"
    evidence = db.scalar(select(EvidenceRecord).where(EvidenceRecord.source_type == "scenario_dialogue", EvidenceRecord.source_id == dialogue.id, EvidenceRecord.evidence_type == "scenario_bundle"))
    if not evidence:
        evidence = EvidenceRecord(
            patient_profile_id=session.patient_profile_id,
            training_session_id=session.id,
            evidence_type="scenario_bundle",
            source_type="scenario_dialogue",
            source_id=dialogue.id,
            source_status=source_status,
            provider="scenario_semantics",
            provider_version=evaluation.scoring_version,
            quality_status="reviewed" if evaluation.review_status in {"confirmed", "adjusted"} else "provisional",
            payload={"contract": dialogue.contract_snapshot, "evidence": evaluation.evidence_snapshot},
            measured_at=evaluation.created_at,
        )
        db.add(evidence)
        db.flush()
    values = {
        "functional_goal": (evaluation.goal_score, "%"),
        "information_units": (evaluation.information_score, "%"),
        "response_effectiveness": (evaluation.response_score, "%"),
        "independence": (evaluation.independence_score, "%"),
    }
    for code, (value, unit) in values.items():
        if db.scalar(select(MetricRecord).where(MetricRecord.source_type == "scenario_dialogue", MetricRecord.source_id == dialogue.id, MetricRecord.code == code)):
            continue
        context = {
            "task_family": "scenario",
            "exercise_contract_version": dialogue.contract_version,
            "prompt_policy": task.prompt_policy_snapshot,
            "maximum_prompt_level": dialogue.maximum_prompt_level,
            "evaluation_role": dialogue.evaluation_role,
        }
        key = hashlib.sha256(json.dumps({"code": code, "context": context, "version": evaluation.scoring_version}, sort_keys=True).encode()).hexdigest()
        db.add(
            MetricRecord(
                patient_profile_id=session.patient_profile_id,
                training_session_id=session.id,
                code=code,
                value=value,
                status="invalid" if source_status == "mock" else "measured",
                unit=unit,
                measured_at=evaluation.created_at,
                measurement_context=context,
                source_type="scenario_dialogue",
                source_id=dialogue.id,
                provider="scenario_semantics",
                algorithm=evaluation.scoring_version,
                version=evaluation.scoring_version,
                quality={"review_status": evaluation.review_status, "source_status": source_status},
                evidence_ids=[str(evidence.id)],
                comparison_key=key,
                decision_eligible=source_status != "mock" and evaluation.review_status in {"confirmed", "adjusted"},
            )
        )
    db.commit()
    refresh_longitudinal_insights(db, session.patient_profile_id)


def _session_counts(session: TrainingSession):
    statuses = [task.v2_status for task in session.session_tasks]
    return {
        "planned_exercises": len(statuses),
        "completed_exercises": statuses.count("completed"),
        "skipped_exercises": statuses.count("skipped"),
        "technical_invalid_exercises": statuses.count("technical_invalid"),
        "independent_completed_exercises": sum(1 for task in session.session_tasks if task.v2_status == "completed" and task.prompt_level == 0),
        "prompted_completed_exercises": sum(1 for task in session.session_tasks if task.v2_status == "completed" and task.prompt_level > 0),
    }


def _create_summary(db: Session, session: TrainingSession):
    existing = db.scalar(select(TrainingSessionSummary).where(TrainingSessionSummary.training_session_id == session.id))
    if existing:
        return existing
    counts = _session_counts(session)
    metric_rows = list(db.scalars(select(MetricRecord).where(MetricRecord.training_session_id == session.id, MetricRecord.status == "measured")))
    observations = []
    if counts["independent_completed_exercises"]:
        observations.append("今天有练习是在没有完整提示的情况下完成的。")
    if counts["technical_invalid_exercises"]:
        observations.append("部分练习因技术原因未能评分，不代表你的能力下降。")
    if not observations:
        observations.append("今天的训练记录已经保存，可以按计划继续练习。")
    comparisons = []
    for code in sorted({item.code for item in metric_rows}):
        history = list(db.scalars(select(MetricRecord).where(MetricRecord.patient_profile_id == session.patient_profile_id, MetricRecord.code == code).order_by(MetricRecord.measured_at)))
        comparable = build_comparable_set(history)
        fact = trend_fact(history, comparable)
        if fact.get("status") == "measured":
            comparisons.append({"code": code, "label": METRIC_LABELS.get(code, code), "trend": fact, "explanation": _trend_explanation(code, fact)})
    summary = TrainingSessionSummary(
        training_session_id=session.id,
        patient_profile_id=session.patient_profile_id,
        facts={**counts, "metric_count": len(metric_rows)},
        patient_observations=observations,
        comparison_to_previous={"status": "measured", "items": comparisons} if comparisons else {"status": "insufficient", "items": []},
        next_training_focus="下一次继续按照治疗师发布的训练方案完成练习。",
        generation_method="deterministic_template",
        source_status="real",
    )
    db.add(summary)
    session.summary_status = "ready"
    return summary


def _derive_milestones(db: Session, session: TrainingSession):
    for task in session.session_tasks:
        if task.v2_status == "completed" and task.prompt_level == 0:
            key = f"first-independent:{task.exercise_type_snapshot or 'exercise'}"
            if not db.scalar(select(Milestone).where(Milestone.patient_profile_id == session.patient_profile_id, Milestone.dedup_key == key)):
                db.add(
                    Milestone(
                        patient_profile_id=session.patient_profile_id,
                        code="first_independent_completion",
                        title="第一次独立完成",
                        description="你第一次在不使用完整示范的情况下完成了这类练习。",
                        dedup_key=key,
                        trigger_facts={"training_session_id": str(session.id), "session_task_id": str(task.id)},
                        evidence_ids=[],
                    )
                )


def session_summary(db: Session, user: User, session_id: UUID):
    session = _session_owned(db, user, session_id)
    summary = db.scalar(select(TrainingSessionSummary).where(TrainingSessionSummary.training_session_id == session.id))
    if not summary and session.v2_status == "completed":
        summary = _create_summary(db, session)
        db.commit()
    if not summary:
        raise HTTPException(status_code=409, detail="训练尚未完成")
    return {
        "session_id": str(session.id),
        "facts": summary.facts,
        "patient_observations": summary.patient_observations,
        "comparison_to_previous": summary.comparison_to_previous,
        "next_training_focus": summary.next_training_focus,
        "generation_method": summary.generation_method,
    }


def _metric_trends(db: Session, profile_id: UUID):
    result = []
    for code in ("script_accuracy", "speech_rate", "error_count", "loudness", "independence"):
        rows = list(
            db.scalars(
                select(MetricRecord)
                .where(MetricRecord.patient_profile_id == profile_id, MetricRecord.code == code)
                .order_by(MetricRecord.measured_at.asc())
            )
        )
        comparable = build_comparable_set(rows)
        fact = trend_fact(rows, comparable)
        result.append(
            {
                "code": code,
                "label": METRIC_LABELS.get(code, code),
                "comparability": comparable.__dict__,
                "trend": fact,
                "explanation": _trend_explanation(code, fact),
            }
        )
    return result


def _trend_explanation(code: str, fact: dict):
    if fact.get("status") != "measured":
        return "还需要更多在相同训练条件下完成的记录，才能判断变化。"
    delta = fact["delta"]
    if abs(delta) < 0.01:
        return "最近几次可比较记录总体稳定。"
    direction = "上升" if delta > 0 else "下降"
    if code == "error_count":
        direction = "减少" if delta < 0 else "增加"
    return f"最近 {fact['sample_count']} 次可比较记录呈{direction}变化；这是训练事实趋势，不代表诊断结论。"


def refresh_longitudinal_insights(db: Session, profile_id: UUID):
    """Materialize conservative facts-to-observation-to-recommendation records.

    Only real, decision-eligible comparable measurements can enter this path.
    Recommendations remain candidates until a therapist makes a decision.
    """
    for code in ("script_accuracy", "speech_rate", "independence"):
        rows = list(db.scalars(select(MetricRecord).where(MetricRecord.patient_profile_id == profile_id, MetricRecord.code == code).order_by(MetricRecord.measured_at)))
        comparable = build_comparable_set(rows)
        fact = trend_fact(rows, comparable)
        if fact.get("status") != "measured" or fact.get("sample_count", 0) < 3:
            continue
        supporting = comparable.included_measurement_ids
        latest = db.scalar(select(ObservationRecord).where(ObservationRecord.patient_profile_id == profile_id, ObservationRecord.scope == f"trend:{code}").order_by(ObservationRecord.created_at.desc()))
        if latest and latest.supporting_metric_ids == supporting:
            continue
        direction = "上升" if fact["delta"] > 0 else "下降" if fact["delta"] < 0 else "保持稳定"
        observation = ObservationRecord(
            patient_profile_id=profile_id,
            statement=f"在相同测量条件下，{METRIC_LABELS.get(code, code)}最近 {fact['sample_count']} 次记录总体{direction}。",
            scope=f"trend:{code}",
            time_window={"from": fact.get("from"), "to": fact.get("to")},
            supporting_metric_ids=supporting,
            supporting_evidence_ids=sorted({evidence_id for row in rows if str(row.id) in supporting for evidence_id in row.evidence_ids}),
            generator="deterministic",
            generator_version="trend-observation-v1",
            confidence=0.8,
            limitations=["仅描述可比较训练记录", "不构成诊断或疗效结论"],
            source_status="real",
        )
        db.add(observation)
        db.flush()
        recommendation = RecommendationRecord(
            patient_profile_id=profile_id,
            scope=f"trend:{code}",
            candidate_action="建议治疗师结合原始证据复核，并决定是否保持或调整下一版训练方案。",
            basis_observation_ids=[str(observation.id)],
            generator="deterministic",
            generator_version="trend-recommendation-v1",
            status="proposed",
            source_status="real",
        )
        db.add(recommendation)
        if fact["delta"] < 0:
            create_attention(
                db,
                profile_id,
                "comparable_metric_decline",
                "comparable_trend_decline",
                f"{METRIC_LABELS.get(code, code)}在可比较记录中出现下降趋势，请治疗师复核原始证据。",
                f"trend-decline:{code}:{supporting[-1]}",
                [{"type": "metric", "id": item} for item in supporting],
                priority="normal",
                evidence_ids=observation.supporting_evidence_ids,
            )
    db.commit()


def patient_progress(db: Session, user: User):
    profile = get_patient_profile(db, user)
    sessions = list(
        db.scalars(
            select(TrainingSession)
            .where(TrainingSession.patient_profile_id == profile.id, TrainingSession.session_kind == "formal")
            .order_by(TrainingSession.local_session_date.desc())
        )
    )
    milestones = list(db.scalars(select(Milestone).where(Milestone.patient_profile_id == profile.id).order_by(Milestone.achieved_at.desc()).limit(20)))
    completed = sum(1 for item in sessions if item.v2_status == "completed")
    return {
        "recent_summary": "已经开始积累训练记录。" if sessions else "完成第一次训练后，这里会显示变化。",
        "comparable_trends": _metric_trends(db, profile.id),
        "milestones": [
            {"id": str(item.id), "code": item.code, "title": item.title, "description": item.description, "achieved_at": item.achieved_at.isoformat(), "source_status": (item.trigger_facts or {}).get("source_status", "real")}
            for item in milestones
        ],
        "training_adherence": {
            "formal_sessions": len(sessions),
            "completed_sessions": completed,
            "status": "measured" if sessions else "insufficient",
        },
        "insufficient_data": not any(item["trend"]["status"] == "measured" for item in _metric_trends(db, profile.id)),
    }


def patient_home(db: Session, user: User):
    profile = get_patient_profile(db, user)
    goal = _active_goal(db, profile.id)
    plan = _active_plan(db, profile.id)
    session = None
    if plan:
        today = _patient_today(profile)
        session = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.local_session_date == today,
                TrainingSession.session_kind == "formal",
                TrainingSession.v2_status.in_(["in_progress", "paused"]),
            )
            .order_by(TrainingSession.started_at.desc())
        ) or db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.formal_training_plan_version_id == plan.id,
                TrainingSession.local_session_date == today,
                TrainingSession.session_kind == "formal",
            )
        )
    if profile.onboarding_status != "ready":
        state = "onboarding_required"
    elif not plan:
        state = "waiting_for_plan"
    elif session and session.formal_training_plan_version_id != plan.id:
        state = "plan_updated"
    elif session and session.v2_status == "completed":
        state = "completed"
    elif session and session.v2_status == "paused":
        state = "paused"
    elif session:
        state = "in_progress"
    else:
        pending_review = db.scalar(
            select(StageReview.id).where(
                StageReview.patient_profile_id == profile.id,
                StageReview.status == "draft",
            )
        )
        state = "stage_review_pending" if pending_review else "ready_to_train"
    session_data = session_dict(db, session) if session else None
    trends = [item for item in _metric_trends(db, profile.id) if item["trend"]["status"] == "measured"][:2]
    if state == "completed":
        primary_action = {"label": "查看今天总结", "action": "view_summary"}
    elif session:
        primary_action = {"label": "继续今天的训练", "action": "resume_session"}
    elif state in {"ready_to_train", "plan_updated", "stage_review_pending"}:
        primary_action = {"label": "开始今天的训练", "action": "start_session"}
    else:
        primary_action = None
    return {
        "state": state,
        "greeting": f"你好，{user.username}",
        "active_rehabilitation_goal": goal_dict(goal),
        "active_training_plan": plan_dict(plan) if plan else None,
        "stage_focus": plan.stage_focus if plan else None,
        "today_session": session_data,
        "today_training_structure": plan_dict(plan).get("exercise_rules", []) if plan else [],
        "estimated_duration": (plan.strategy_snapshot or {}).get("duration") if plan else None,
        "primary_action": primary_action,
        "recent_comparable_changes": trends,
        "plan_update_announcement": "治疗师已发布新的训练方案；完成当前训练后，新方案会从下一次新建训练开始生效。" if session and session.formal_training_plan_version_id != plan.id else None,
        "plan_update_ack_state": "pending" if state == "plan_updated" else "not_required",
    }


def update_patient_timezone(db: Session, user: User, timezone_name: str):
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="未知时区") from exc
    profile = get_patient_profile(db, user)
    profile.timezone = timezone_name
    db.commit()
    return {"timezone": profile.timezone}


def create_attention(db: Session, profile_id: UUID, item_type: str, trigger_code: str, summary: str, dedup_key: str, source_refs: list, priority: str = "normal", evidence_ids: list | None = None):
    existing = db.scalar(
        select(AttentionItem).where(
            AttentionItem.patient_profile_id == profile_id,
            AttentionItem.dedup_key == dedup_key,
            AttentionItem.status.in_(["open", "acknowledged"]),
        )
    )
    if existing:
        return existing
    row = AttentionItem(
        patient_profile_id=profile_id,
        item_type=item_type,
        trigger_code=trigger_code,
        trigger_facts={"rule_version": "attention-v1"},
        source_refs=source_refs,
        evidence_ids=evidence_ids or [],
        dedup_key=dedup_key,
        priority=priority,
        summary=summary,
        status="open",
    )
    db.add(row)
    db.flush()
    return row


def attention_dict(db: Session, row: AttentionItem):
    profile = db.get(PatientProfile, row.patient_profile_id)
    patient = db.get(User, profile.user_id) if profile else None
    return {
        "id": str(row.id),
        "patient_user_id": str(patient.id) if patient else None,
        "patient": patient.username if patient else "未知患者",
        "type": row.item_type,
        "trigger_code": row.trigger_code,
        "trigger_facts": row.trigger_facts,
        "source_refs": row.source_refs,
        "evidence_ids": row.evidence_ids,
        "priority": row.priority,
        "summary": row.summary,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def therapist_workbench(db: Session, actor: User):
    assigned_ids = select(TherapistPatientAssignment.patient_profile_id).where(
        TherapistPatientAssignment.therapist_user_id == actor.id,
        TherapistPatientAssignment.status == "active",
    )
    stmt = select(AttentionItem).where(AttentionItem.status.in_(["open", "acknowledged"]))
    if actor.role != UserRole.admin:
        stmt = stmt.where(AttentionItem.patient_profile_id.in_(assigned_ids))
    rows = list(db.scalars(stmt.order_by(AttentionItem.created_at.asc())))
    return {
        "summary": {"open": sum(item.status == "open" for item in rows), "acknowledged": sum(item.status == "acknowledged" for item in rows)},
        "attention_items": [attention_dict(db, item) for item in rows],
        "generated_at": utc_now().isoformat(),
    }


def set_attention_status(db: Session, actor: User, item_id: UUID, new_status: str, note: str | None = None):
    item = db.get(AttentionItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="关注事项不存在")
    profile = db.get(PatientProfile, item.patient_profile_id)
    _therapist_profile(db, actor, profile.user_id)
    if new_status == "acknowledged":
        item.status = "acknowledged"
        item.assigned_to_user_id = actor.id
        item.acknowledged_at = utc_now()
    elif new_status in {"resolved", "dismissed"}:
        item.status = new_status
        item.assigned_to_user_id = actor.id
        item.resolved_at = utc_now()
        item.resolution_note = note
    else:
        raise HTTPException(status_code=422, detail="无效关注事项状态")
    db.commit()
    return attention_dict(db, item)


def therapist_session_detail(db: Session, actor: User, session_id: UUID):
    session = db.scalar(select(TrainingSession).options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template)).where(TrainingSession.id == session_id))
    if not session:
        raise HTTPException(status_code=404, detail="训练记录不存在")
    profile = db.get(PatientProfile, session.patient_profile_id)
    _therapist_profile(db, actor, profile.user_id)
    metrics = list(db.scalars(select(MetricRecord).where(MetricRecord.training_session_id == session.id).order_by(MetricRecord.measured_at)))
    evidence = list(db.scalars(select(EvidenceRecord).where(EvidenceRecord.training_session_id == session.id).order_by(EvidenceRecord.measured_at)))
    observations = list(db.scalars(select(ObservationRecord).where(ObservationRecord.patient_profile_id == profile.id).order_by(ObservationRecord.created_at.desc()).limit(10)))
    recommendations = list(db.scalars(select(RecommendationRecord).where(RecommendationRecord.patient_profile_id == profile.id).order_by(RecommendationRecord.created_at.desc()).limit(10)))
    return {
        "overview": session_dict(db, session),
        "evidence": [evidence_dict(item) for item in evidence],
        "metrics": [metric_dict(item) for item in metrics],
        "professional_metrics": professional_metric_panel(db, profile.id, session.id),
        "comparability": [
            {"code": code, "result": build_comparable_set([item for item in metrics if item.code == code]).__dict__}
            for code in sorted({item.code for item in metrics})
        ],
        "observations": [observation_dict(item) for item in observations],
        "recommendations": [recommendation_dict(item) for item in recommendations],
        "therapist_actions": ["acknowledge", "add_note", "open_stage_review", "create_plan_version"],
    }


def evidence_dict(item: EvidenceRecord):
    return {"id": str(item.id), "type": item.evidence_type, "source_type": item.source_type, "source_id": str(item.source_id), "source_status": item.source_status, "provider": item.provider, "provider_version": item.provider_version, "quality_status": item.quality_status, "payload": item.payload, "measured_at": item.measured_at.isoformat()}


def metric_dict(item: MetricRecord):
    return {"id": str(item.id), "code": item.code, "label": METRIC_LABELS.get(item.code, item.code), "value": item.value, "status": item.status, "unit": item.unit, "measured_at": item.measured_at.isoformat(), "measurement_context": item.measurement_context, "source": {"type": item.source_type, "id": str(item.source_id)}, "provider": item.provider, "algorithm": item.algorithm, "instrument": item.instrument, "version": item.version, "quality": item.quality, "evidence_ids": item.evidence_ids, "comparison_key": item.comparison_key, "decision_eligible": item.decision_eligible}


def observation_dict(item: ObservationRecord):
    return {"id": str(item.id), "statement": item.statement, "scope": item.scope, "time_window": item.time_window, "supporting_metric_ids": item.supporting_metric_ids, "supporting_evidence_ids": item.supporting_evidence_ids, "generator": item.generator, "generator_version": item.generator_version, "confidence": item.confidence, "limitations": item.limitations}


def recommendation_dict(item: RecommendationRecord):
    return {"id": str(item.id), "scope": item.scope, "candidate_action": item.candidate_action, "basis_observation_ids": item.basis_observation_ids, "generator": item.generator, "generator_version": item.generator_version, "status": item.status}


def professional_metric_panel(db: Session, profile_id: UUID, session_id: UUID):
    current = {item.code: item for item in db.scalars(select(MetricRecord).where(MetricRecord.training_session_id == session_id))}
    assessment = db.scalar(select(AssessmentSession).where(AssessmentSession.patient_profile_id == profile_id).order_by(AssessmentSession.assessed_at.desc()))
    output = []
    for code, label in METRIC_LABELS.items():
        if code in current:
            payload = metric_dict(current[code])
            payload.update({"display_source": "current_training_session"})
        elif code == "wab_reliability":
            payload = {"code": code, "label": label, "value": None, "status": "unsupported", "unit": None, "display_source": "unsupported", "message": "当前系统尚未支持该指标"}
        elif (
            code in ASSESSMENT_METRICS
            and assessment
            and (assessment.metrics or {}).get(code) is not None
        ):
            payload = {"code": code, "label": label, "value": assessment.metrics.get(code), "status": "measured", "unit": assessment.score_unit, "display_source": "latest_formal_assessment", "measured_at": assessment.assessed_at.isoformat(), "instrument": assessment.instrument_name, "version": assessment.instrument_version}
        elif code in ASSESSMENT_METRICS:
            payload = {"code": code, "label": label, "value": None, "status": "not_administered", "unit": None, "display_source": "formal_assessment", "message": "最近一次正式评估未施测该指标"}
        else:
            payload = {"code": code, "label": label, "value": None, "status": "not_observed", "unit": None, "display_source": "current_training_session", "message": "本次训练未测得该指标"}
        output.append(payload)
    return output


def patient_workspace(db: Session, actor: User, patient_user_id: UUID):
    profile = _therapist_profile(db, actor, patient_user_id)
    patient = db.get(User, patient_user_id)
    goal = _active_goal(db, profile.id)
    plan = _active_plan(db, profile.id)
    sessions = list(db.scalars(select(TrainingSession).where(TrainingSession.patient_profile_id == profile.id).order_by(TrainingSession.created_at.desc()).limit(20)))
    attention = list(db.scalars(select(AttentionItem).where(AttentionItem.patient_profile_id == profile.id, AttentionItem.status.in_(["open", "acknowledged"])).order_by(AttentionItem.created_at.desc())))
    reviews = list(db.scalars(select(StageReview).where(StageReview.patient_profile_id == profile.id).order_by(StageReview.created_at.desc()).limit(10)))
    assessments = list(db.scalars(select(AssessmentSession).where(AssessmentSession.patient_profile_id == profile.id).order_by(AssessmentSession.assessed_at.desc()).limit(10)))
    return {
        "patient": {"user_id": str(patient.id), "profile_id": str(profile.id), "username": patient.username, "timezone": profile.timezone},
        "rehabilitation_goal": goal_dict(goal),
        "active_training_plan": plan_dict(plan) if plan else None,
        "training_adherence": {"formal_session_count": sum(item.session_kind == "formal" for item in sessions), "completed_count": sum(item.v2_status == "completed" for item in sessions)},
        "recent_comparable_changes": [item for item in _metric_trends(db, profile.id) if item["trend"]["status"] == "measured"],
        "observations": [observation_dict(item) for item in db.scalars(select(ObservationRecord).where(ObservationRecord.patient_profile_id == profile.id).order_by(ObservationRecord.created_at.desc()).limit(10))],
        "open_attention_items": [attention_dict(db, item) for item in attention],
        "training_history": [{"id": str(item.id), "date": item.local_session_date.isoformat() if item.local_session_date else None, "status": item.v2_status, "kind": item.session_kind, "plan_version_id": str(item.formal_training_plan_version_id) if item.formal_training_plan_version_id else None} for item in sessions],
        "stage_reviews": [stage_review_dict(item) for item in reviews],
        "formal_assessments": [{"id": str(item.id), "instrument": item.instrument_name, "version": item.instrument_version, "assessed_at": item.assessed_at.isoformat(), "review_status": item.review_status} for item in assessments],
    }


def create_stage_review(db: Session, actor: User, patient_user_id: UUID, payload: StageReviewCreate):
    profile = _therapist_profile(db, actor, patient_user_id)
    plan = _active_plan(db, profile.id)
    metric_stmt = select(MetricRecord).where(MetricRecord.patient_profile_id == profile.id, MetricRecord.decision_eligible.is_(True))
    if payload.review_from:
        metric_stmt = metric_stmt.where(MetricRecord.measured_at >= payload.review_from)
    if payload.review_to:
        metric_stmt = metric_stmt.where(MetricRecord.measured_at <= payload.review_to)
    metrics = list(db.scalars(metric_stmt.order_by(MetricRecord.measured_at)))
    observations = list(db.scalars(select(ObservationRecord).where(ObservationRecord.patient_profile_id == profile.id)))
    recommendations = list(db.scalars(select(RecommendationRecord).where(RecommendationRecord.patient_profile_id == profile.id, RecommendationRecord.status == "proposed")))
    attention = list(db.scalars(select(AttentionItem).where(AttentionItem.patient_profile_id == profile.id, AttentionItem.status.in_(["open", "acknowledged"]))))
    assessments = list(db.scalars(select(AssessmentSession).where(AssessmentSession.patient_profile_id == profile.id)))
    clinical_runs = list(db.scalars(select(EvaluationRun).where(EvaluationRun.patient_profile_id == profile.id, EvaluationRun.domain == "clinical_stage")))
    review = StageReview(
        patient_profile_id=profile.id,
        training_plan_version_id=plan.id if plan else None,
        created_by_user_id=actor.id,
        status="draft",
        review_window={"from": payload.review_from.isoformat() if payload.review_from else None, "to": payload.review_to.isoformat() if payload.review_to else None},
        facts_snapshot={"metrics": [metric_dict(item) for item in metrics], "trends": _metric_trends(db, profile.id)},
        observation_ids=[str(item.id) for item in observations],
        recommendation_ids=[str(item.id) for item in recommendations],
        attention_item_ids=[str(item.id) for item in attention],
        assessment_ids=[str(item.id) for item in assessments],
        clinical_stage_run_ids=[str(item.id) for item in clinical_runs],
        therapist_notes=payload.therapist_notes,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return stage_review_detail(db, actor, review.id)


def stage_review_dict(review: StageReview):
    return {"id": str(review.id), "status": review.status, "training_plan_version_id": str(review.training_plan_version_id) if review.training_plan_version_id else None, "review_window": review.review_window, "facts": review.facts_snapshot, "observation_ids": review.observation_ids, "recommendation_ids": review.recommendation_ids, "attention_item_ids": review.attention_item_ids, "assessment_ids": review.assessment_ids, "clinical_stage_run_ids": review.clinical_stage_run_ids, "therapist_notes": review.therapist_notes, "created_at": review.created_at.isoformat(), "finalized_at": review.finalized_at.isoformat() if review.finalized_at else None}


def stage_review_detail(db: Session, actor: User, review_id: UUID):
    review = db.get(StageReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="阶段复核不存在")
    profile = db.get(PatientProfile, review.patient_profile_id)
    _therapist_profile(db, actor, profile.user_id)
    payload = stage_review_dict(review)
    payload["observations"] = [observation_dict(item) for item in db.scalars(select(ObservationRecord).where(ObservationRecord.id.in_([UUID(item) for item in review.observation_ids])))] if review.observation_ids else []
    payload["recommendations"] = [recommendation_dict(item) for item in db.scalars(select(RecommendationRecord).where(RecommendationRecord.id.in_([UUID(item) for item in review.recommendation_ids])))] if review.recommendation_ids else []
    payload["attention_items"] = [attention_dict(db, item) for item in db.scalars(select(AttentionItem).where(AttentionItem.id.in_([UUID(item) for item in review.attention_item_ids])))] if review.attention_item_ids else []
    assessments = (
        list(
            db.scalars(
                select(AssessmentSession).where(
                    AssessmentSession.id.in_([UUID(item) for item in review.assessment_ids])
                )
            )
        )
        if review.assessment_ids
        else []
    )
    payload["formal_assessments"] = [
        {
            "id": str(item.id),
            "instrument_name": item.instrument_name,
            "instrument_version": item.instrument_version,
            "assessed_at": item.assessed_at.isoformat(),
            "review_status": item.review_status,
            "measured_metrics": sorted(
                key for key, value in (item.metrics or {}).items() if value is not None
            ),
            "missing_items": item.missing_items,
        }
        for item in assessments
    ]
    clinical_runs = (
        list(
            db.scalars(
                select(EvaluationRun).where(
                    EvaluationRun.id.in_([UUID(item) for item in review.clinical_stage_run_ids])
                )
            )
        )
        if review.clinical_stage_run_ids
        else []
    )
    payload["clinical_stage_support"] = [
        {
            "id": str(item.id),
            "result_status": _enum_value(item.result_status),
            "adoption_status": _enum_value(item.adoption_status),
            "algorithm_version": item.algorithm_version,
            "created_at": item.created_at.isoformat(),
        }
        for item in clinical_runs
    ]
    return payload


def create_decision(db: Session, actor: User, review_id: UUID, payload: DecisionCreate):
    review = db.get(StageReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="阶段复核不存在")
    profile = db.get(PatientProfile, review.patient_profile_id)
    _therapist_profile(db, actor, profile.user_id)
    if review.status == "finalized":
        raise HTTPException(status_code=409, detail="该阶段复核已经形成决策")
    decision = TherapistDecision(
        patient_profile_id=profile.id,
        stage_review_id=review.id,
        actor_user_id=actor.id,
        decision_type=payload.decision_type,
        reason=payload.reason,
        source_attention_item_id=payload.source_attention_item_id,
        payload_snapshot=payload.payload,
        result_snapshot={},
    )
    db.add(decision)
    db.flush()
    if payload.decision_type == "create_new_training_plan_version":
        current = db.get(TrainingPlanVersion, review.training_plan_version_id) if review.training_plan_version_id else _active_plan(db, profile.id)
        if not current:
            raise HTTPException(status_code=409, detail="没有可作为新版本基础的训练方案")
        version = (db.scalar(select(func.max(TrainingPlanVersion.version_number)).where(TrainingPlanVersion.patient_profile_id == profile.id)) or 0) + 1
        draft = TrainingPlanVersion(
            patient_profile_id=profile.id,
            rehabilitation_goal_id=current.rehabilitation_goal_id,
            version_number=version,
            status="draft",
            stage_focus=str(payload.payload.get("stage_focus") or current.stage_focus),
            strategy_snapshot={**current.strategy_snapshot, **payload.payload.get("strategy", {})},
            supersedes_id=current.id,
            source_decision_id=decision.id,
        )
        db.add(draft)
        db.flush()
        current_rules = list(db.scalars(select(TrainingPlanExerciseRule).where(TrainingPlanExerciseRule.training_plan_version_id == current.id)))
        for item in current_rules:
            db.add(TrainingPlanExerciseRule(training_plan_version_id=draft.id, task_template_id=item.task_template_id, exercise_type=item.exercise_type, order_index=item.order_index, target_repetitions=item.target_repetitions, difficulty=item.difficulty, max_information_units=item.max_information_units, prompt_policy=item.prompt_policy, scene_scope=item.scene_scope))
        decision.resulting_training_plan_version_id = draft.id
        decision.result_snapshot = {"draft_training_plan_version_id": str(draft.id), "requires_publish": True}
    else:
        decision.result_snapshot = {"status": "recorded"}
    review.status = "finalized"
    review.finalized_at = utc_now()
    if payload.source_attention_item_id:
        item = db.get(AttentionItem, payload.source_attention_item_id)
        if item and item.patient_profile_id == profile.id:
            item.status = "resolved"
            item.resolved_at = utc_now()
            item.resolution_note = f"由阶段复核决策 {decision.id} 处理"
    db.commit()
    db.refresh(decision)
    return {"id": str(decision.id), "stage_review_id": str(decision.stage_review_id), "decision_type": decision.decision_type, "reason": decision.reason, "payload": decision.payload_snapshot, "result": decision.result_snapshot, "resulting_training_plan_version_id": str(decision.resulting_training_plan_version_id) if decision.resulting_training_plan_version_id else None, "decided_at": decision.decided_at.isoformat()}


def create_formal_assessment(db: Session, actor: User, patient_user_id: UUID, payload: FormalAssessmentCreate):
    profile = _therapist_profile(db, actor, patient_user_id)
    unknown_metrics = sorted(set(payload.metrics) - ASSESSMENT_METRICS - {"wab_reliability"})
    if unknown_metrics:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的正式评估指标：{', '.join(unknown_metrics)}",
        )
    metrics = {key: value for key, value in payload.metrics.items() if key != "wab_reliability" and value is not None}
    assessment = AssessmentSession(
        patient_profile_id=profile.id,
        assessment_type=AssessmentType.during,
        evaluation_source=EvaluationSource.human,
        review_status=AssessmentReviewStatus.confirmed.value,
        reviewed_by_user_id=actor.id,
        reviewed_at=utc_now(),
        assessed_at=payload.assessed_at or utc_now(),
        metrics=metrics,
        notes=payload.notes,
        therapist_notes="通过 Product v2 正式评估入口创建。",
        instrument_name=payload.instrument_name,
        instrument_version=payload.instrument_version,
        language_locale=payload.language_locale,
        assessment_stage="formal",
        administered_by_user_id=actor.id,
        administrator_role="therapist",
        raw_item_results=payload.raw_item_results,
        subscale_results=payload.subscale_results,
        total_result=payload.total_result,
        missing_items=payload.missing_items,
        score_unit=payload.score_unit,
        administration_mode=payload.administration_mode,
        protocol_deviations=payload.protocol_deviations,
        protocol_deviation_reasons=payload.protocol_deviation_reasons,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    try:
        from app.modules.evaluation_runs.clinical_stage_v3 import write_clinical_stage_run
        write_clinical_stage_run(db, assessment.id)
    except Exception:
        db.rollback()
        from app.modules.evaluation_runs.clinical_stage_v3 import ALGORITHM_VERSION
        from app.modules.evaluation_runs.service import record_evaluation_write_failure
        record_evaluation_write_failure(db, source_type="assessment_session", source_id=assessment.id, domain="clinical_stage", algorithm_version=ALGORITHM_VERSION, failure_stage="shadow_write")
    return {"id": str(assessment.id), "instrument_name": assessment.instrument_name, "instrument_version": assessment.instrument_version, "review_status": assessment.review_status, "assessed_at": assessment.assessed_at.isoformat(), "metrics": assessment.metrics, "unsupported_metrics": ["wab_reliability"], "clinical_stage": "internal_shadow"}
