from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.training.model import (
    RecommendationReviewStatus,
    SessionTask,
    TaskTemplate,
    TrainingPlan,
    TrainingPlanItem,
    TrainingRecommendationReview,
    TrainingSession,
    TrainingStatus,
    TrainingType,
)
from app.modules.attempts.model import Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.training.schema import (
    RecommendationEffectRead,
    RecommendationEffectSummaryRead,
    TaskTemplateRead,
    TrainingRecommendationRead,
    TrainingRecommendationReviewUpdate,
)
from app.modules.users.model import PatientProfile, User, UserRole
from app.modules.users.service import get_patient_profile


SEED_TASKS = [
    {
        "task_type": TrainingType.repeat,
        "title": "短句跟读",
        "instruction": "请跟我说这一句。",
        "target_text": "今天天气很好。",
        "content_level": "L2",
        "autonomy_level": "S1",
    },
    {
        "task_type": TrainingType.scenario,
        "title": "医院看病场景",
        "instruction": "请说说在医院看病时你想表达什么。",
        "target_text": "我想去医院看病，请医生帮我检查。",
        "content_level": "L4",
        "autonomy_level": "S3",
        "scene_prompt": "医院看病",
    },
]


def ensure_seed_tasks(db: Session) -> None:
    exists = db.scalar(select(TaskTemplate.id).limit(1))
    if exists:
        return
    for item in SEED_TASKS:
        db.add(TaskTemplate(**item, scoring_config={"mode": "mock"}))
    db.commit()


def get_training_types() -> list[str]:
    return [TrainingType.repeat.value, TrainingType.scenario.value]


def get_training_recommendation(db: Session, user: User) -> TrainingRecommendationRead:
    ensure_seed_tasks(db)
    profile = get_patient_profile(db, user)
    return get_patient_training_recommendation(db, profile.id, include_review_override=True)


def get_patient_training_recommendation(
    db: Session,
    patient_profile_id: UUID,
    include_review_override: bool = True,
) -> TrainingRecommendationRead:
    ensure_seed_tasks(db)
    from app.modules.profiles.service import refresh_ability_profile

    ability = refresh_ability_profile(db, patient_profile_id)
    recommended_type, headline, reason, focus_points, minutes = decide_recommendation(ability)
    system_recommendation = build_recommendation_read(
        db=db,
        recommended_type=recommended_type,
        headline=headline,
        reason=reason,
        focus_points=focus_points,
        suggested_minutes=minutes,
        content_level=ability.current_content_level,
        autonomy_level=ability.current_autonomy_level,
        confidence=ability.confidence,
        profile_summary=ability.assessment_summary,
        source="system",
        review_status=RecommendationReviewStatus.pending_review.value,
    )
    review = latest_recommendation_review(db, patient_profile_id)
    if not include_review_override or not review:
        return system_recommendation
    if review.review_status not in {RecommendationReviewStatus.confirmed, RecommendationReviewStatus.adjusted}:
        return system_recommendation
    return recommendation_review_to_read(db, review)


def get_patient_recommendation_for_therapist(db: Session, patient_user_id: UUID) -> TrainingRecommendationRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    return get_patient_training_recommendation(db, profile.id, include_review_override=False)


def save_patient_recommendation_review(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    payload: TrainingRecommendationReviewUpdate,
) -> TrainingRecommendationRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    system_recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=False)
    status_value = (
        RecommendationReviewStatus.confirmed
        if payload.recommended_type == system_recommendation.recommended_type
        and payload.headline == system_recommendation.headline
        and payload.reason == system_recommendation.reason
        and payload.focus_points == system_recommendation.focus_points
        and payload.suggested_minutes == system_recommendation.suggested_minutes
        else RecommendationReviewStatus.adjusted
    )
    review = TrainingRecommendationReview(
        patient_profile_id=profile.id,
        recommended_type=payload.recommended_type,
        headline=payload.headline.strip() or system_recommendation.headline,
        reason=payload.reason.strip() or system_recommendation.reason,
        focus_points=[point.strip() for point in payload.focus_points if point.strip()][:5],
        suggested_minutes=max(5, min(payload.suggested_minutes, 30)),
        content_level=system_recommendation.content_level,
        autonomy_level=system_recommendation.autonomy_level,
        confidence=system_recommendation.confidence,
        profile_summary=system_recommendation.profile_summary,
        review_status=status_value,
        reviewed_by_user_id=therapist.id,
        therapist_notes=payload.therapist_notes,
    )
    if not review.focus_points:
        review.focus_points = system_recommendation.focus_points
    db.add(review)
    db.commit()
    db.refresh(review)
    return recommendation_review_to_read(db, review)


def get_patient_recommendation_effects(db: Session, patient_user_id: UUID) -> RecommendationEffectSummaryRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    sessions = list(
        db.scalars(
            select(TrainingSession)
            .where(
                TrainingSession.patient_profile_id == profile.id,
                TrainingSession.recommendation_source.is_not(None),
            )
            .order_by(TrainingSession.created_at.desc())
            .limit(8)
        )
    )
    effects = [build_recommendation_effect(db, session) for session in sessions]
    completed_count = sum(1 for effect in effects if effect.status == TrainingStatus.completed.value)
    matched_count = sum(1 for effect in effects if effect.recommendation_matched)
    trend = analyze_recommendation_trend(effects)
    return RecommendationEffectSummaryRead(
        total_recommended_sessions=len(effects),
        completed_recommended_sessions=completed_count,
        matched_sessions=matched_count,
        trend_status=trend["status"],
        trend_summary=trend["summary"],
        strategy_hint=trend["hint"],
        evidence_points=trend["evidence"],
        latest=effects,
    )


def build_recommendation_effect(db: Session, session: TrainingSession) -> RecommendationEffectRead:
    metrics = recommendation_session_metrics(db, session.id)
    return RecommendationEffectRead(
        session_id=session.id,
        created_at=session.created_at,
        training_type=session.training_type,
        recommendation_source=session.recommendation_source,
        recommendation_headline=(session.recommendation_snapshot or {}).get("headline"),
        recommendation_matched=session.recommendation_matched,
        status=session.status.value,
        metrics=metrics,
        summary=effect_summary(metrics, session.status == TrainingStatus.completed),
    )


def recommendation_session_metrics(db: Session, session_id: UUID) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .join(Attempt, Attempt.id == AttemptEvaluation.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .where(
            SessionTask.training_session_id == session_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
    ).all()
    grouped: dict[str, list[float]] = {}
    for metric_name, value in rows:
        grouped.setdefault(metric_name, []).append(float(value))
    return {name: round(sum(values) / len(values), 1) for name, values in grouped.items() if values}


def effect_summary(metrics: dict[str, float], completed: bool) -> str:
    if not completed:
        return "患者已从推荐入口开始训练，但还没有完成评分。"
    if not metrics:
        return "训练已完成，暂时没有可汇总的过程指标。"
    parts = []
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    speech_rate = metrics.get("speech_rate")
    loudness = metrics.get("loudness")
    if accuracy is not None:
        parts.append("表达完整度较好" if accuracy >= 90 else "表达完整度仍需关注")
    if errors is not None:
        parts.append("错误较少" if errors <= 1 else "错误仍偏多")
    if speech_rate is not None:
        parts.append("节奏稳定" if 180 <= speech_rate <= 240 else "节奏需要继续观察")
    if loudness is not None:
        parts.append("音量稳定" if 60 <= loudness <= 78 else "音量需要继续观察")
    return "；".join(parts) + "。"


def analyze_recommendation_trend(effects: list[RecommendationEffectRead]) -> dict:
    completed = [effect for effect in reversed(effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    if len(completed) < 2:
        return {
            "status": "observing",
            "summary": "推荐后完成训练次数还不够，暂时只适合观察。",
            "hint": "建议继续保持当前推荐，并等待至少两次完成评分后再判断是否调整。",
            "evidence": [f"已完成推荐训练 {len(completed)} 次"],
        }

    first = completed[0]
    latest = completed[-1]
    deltas = metric_deltas(first.metrics, latest.metrics)
    evidence = build_trend_evidence(deltas)
    positive = 0
    negative = 0
    if deltas.get("script_accuracy", 0) >= 3:
        positive += 1
    elif deltas.get("script_accuracy", 0) <= -3:
        negative += 1
    if deltas.get("error_count", 0) <= -1:
        positive += 1
    elif deltas.get("error_count", 0) >= 1:
        negative += 1
    if "speech_rate" in deltas and speech_rate_better(first.metrics.get("speech_rate"), latest.metrics.get("speech_rate")):
        positive += 1
    if "loudness" in deltas and loudness_better(first.metrics.get("loudness"), latest.metrics.get("loudness")):
        positive += 1

    if positive >= 2 and negative == 0:
        return {
            "status": "effective",
            "summary": "推荐后的训练表现正在变好。",
            "hint": "建议继续使用当前推荐方向，下一次可小幅增加句子长度或自主表达比例。",
            "evidence": evidence,
        }
    if negative >= 2:
        return {
            "status": "needs_adjustment",
            "summary": "推荐后的表现没有稳定改善。",
            "hint": "建议治疗师重新检查推荐方向，必要时降低难度或改回更熟悉的跟读训练。",
            "evidence": evidence,
        }
    return {
        "status": "mixed",
        "summary": "推荐后的表现有变化，但趋势还不稳定。",
        "hint": "建议保持当前推荐一到两次，同时关注错误次数和说话节奏是否继续改善。",
        "evidence": evidence,
    }


def metric_deltas(first: dict[str, float], latest: dict[str, float]) -> dict[str, float]:
    return {
        name: round(latest[name] - first[name], 1)
        for name in PROCESS_METRIC_NAMES
        if name in first and name in latest
    }


def build_trend_evidence(deltas: dict[str, float]) -> list[str]:
    labels = {
        "script_accuracy": ("完整度", "%"),
        "error_count": ("错误", "次"),
        "speech_rate": ("语速", "字/min"),
        "loudness": ("音量", "dBA"),
    }
    points = []
    for key, value in deltas.items():
        label, unit = labels.get(key, (key, ""))
        direction = "提升" if value > 0 else "下降" if value < 0 else "持平"
        points.append(f"{label}{direction} {abs(value):g}{unit}")
    return points or ["暂无可比较指标"]


def speech_rate_better(first: float | None, latest: float | None) -> bool:
    if first is None or latest is None:
        return False
    return abs(latest - 210) + 8 < abs(first - 210)


def loudness_better(first: float | None, latest: float | None) -> bool:
    if first is None or latest is None:
        return False
    return abs(latest - 69) + 3 < abs(first - 69)


def latest_recommendation_review(db: Session, patient_profile_id: UUID) -> TrainingRecommendationReview | None:
    return db.scalar(
        select(TrainingRecommendationReview)
        .where(TrainingRecommendationReview.patient_profile_id == patient_profile_id)
        .order_by(TrainingRecommendationReview.created_at.desc())
    )


def build_recommendation_read(
    db: Session,
    recommended_type: TrainingType,
    headline: str,
    reason: str,
    focus_points: list[str],
    suggested_minutes: int,
    content_level: str,
    autonomy_level: str,
    confidence: float,
    profile_summary: str,
    source: str,
    review_status: str,
    review_id: UUID | None = None,
    therapist_notes: str | None = None,
    updated_at=None,
) -> TrainingRecommendationRead:
    template = pick_template_for_recommendation(
        db,
        recommended_type=recommended_type,
        content_level=content_level,
        autonomy_level=autonomy_level,
    )
    return TrainingRecommendationRead(
        id=review_id,
        recommended_type=recommended_type,
        headline=headline,
        reason=reason,
        focus_points=focus_points,
        suggested_minutes=suggested_minutes,
        content_level=content_level,
        autonomy_level=autonomy_level,
        confidence=confidence,
        profile_summary=profile_summary,
        source=source,
        review_status=review_status,
        therapist_notes=therapist_notes,
        updated_at=updated_at,
        task_template=TaskTemplateRead.model_validate(template) if template else None,
    )


def recommendation_review_to_read(db: Session, review: TrainingRecommendationReview) -> TrainingRecommendationRead:
    return build_recommendation_read(
        db=db,
        recommended_type=review.recommended_type,
        headline=review.headline,
        reason=review.reason,
        focus_points=review.focus_points,
        suggested_minutes=review.suggested_minutes,
        content_level=review.content_level,
        autonomy_level=review.autonomy_level,
        confidence=review.confidence,
        profile_summary=review.profile_summary,
        source="therapist",
        review_status=review.review_status.value,
        review_id=review.id,
        therapist_notes=review.therapist_notes,
        updated_at=review.updated_at,
    )


def decide_recommendation(ability) -> tuple[TrainingType, str, str, list[str], int]:
    accuracy = ability.avg_script_accuracy_recent
    errors = ability.avg_error_count_recent
    speech_rate = ability.avg_speech_rate_recent
    loudness = ability.avg_loudness_recent
    reviewed_count = (ability.evidence or {}).get("reviewed_assessment_count", 0)

    if accuracy is None or errors is None:
        return (
            TrainingType.repeat,
            "先从熟悉短句开始",
            "系统还需要几次训练记录来了解你的表达状态，短句跟读最容易形成稳定反馈。",
            ["把一句话说完整", "不用着急，先听清再开口", "完成后查看系统反馈"],
            8,
        )
    if errors >= 3 or accuracy < 78:
        return (
            TrainingType.repeat,
            "今天先稳住一句话",
            "最近表达里需要留意的地方较多，先练短句能减少负担，也方便看清具体进步。",
            ["慢一点说完整", "重点减少漏字和错字", "每次只关注一个小目标"],
            10,
        )
    if loudness is not None and loudness < 60:
        return (
            TrainingType.repeat,
            "先练声音稳定",
            "最近声音偏轻，跟读训练更适合把气息、音量和句子完整度一起稳住。",
            ["坐直后再开始", "先吸气再说句子", "让声音保持到句尾"],
            10,
        )
    if speech_rate is not None and speech_rate < 180:
        return (
            TrainingType.repeat,
            "练一组连贯短句",
            "最近说话节奏偏慢，可以用熟悉短句练习连续表达，重点减少不必要的停顿。",
            ["一句话尽量连起来", "停顿少一点", "保持清楚比追求快更重要"],
            12,
        )
    if ability.current_content_level in {"L3", "L4", "L5"} and ability.current_autonomy_level in {"S3", "S4"}:
        confidence_note = "治疗师复核已经纳入画像。" if reviewed_count else "当前建议来自系统画像，等待治疗师复核后会更稳。"
        return (
            TrainingType.scenario,
            "可以试试生活场景表达",
            f"最近短句表现比较稳定，适合增加一点自主表达。{confidence_note}",
            ["围绕一个生活场景说清需求", "先说重点，再补充细节", "不用追求很长"],
            12,
        )
    return (
        TrainingType.repeat,
        "继续当前节奏",
        "目前适合保持短句练习，让表达完整度和稳定性继续累积。",
        ["每天完成一小组", "关注反馈里的一个建议", "稳定后再增加场景表达"],
        10,
    )


def pick_template_for_recommendation(
    db: Session,
    recommended_type: TrainingType,
    content_level: str,
    autonomy_level: str,
) -> TaskTemplate | None:
    templates = list(db.scalars(select(TaskTemplate).where(TaskTemplate.task_type == recommended_type)))
    if not templates:
        return None
    return min(
        templates,
        key=lambda template: (
            abs(level_number(template.content_level) - level_number(content_level)),
            abs(level_number(template.autonomy_level) - level_number(autonomy_level)),
            template.created_at,
        ),
    )


def level_number(level: str) -> int:
    try:
        return int(level[1:])
    except (TypeError, ValueError):
        return 1


def get_or_create_today_plan(db: Session, user: User) -> TrainingPlan:
    ensure_seed_tasks(db)
    profile = get_patient_profile(db, user)
    plan = db.scalar(
        select(TrainingPlan)
        .where(TrainingPlan.patient_profile_id == profile.id)
        .order_by(TrainingPlan.created_at.desc())
        .options(selectinload(TrainingPlan.items))
    )
    if plan:
        return plan
    plan = TrainingPlan(patient_profile_id=profile.id, title="今日训练")
    db.add(plan)
    db.flush()
    templates = list(db.scalars(select(TaskTemplate).order_by(TaskTemplate.created_at.asc())))
    for index, template in enumerate(templates):
        db.add(TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=index))
    db.commit()
    return db.scalar(
        select(TrainingPlan).where(TrainingPlan.id == plan.id).options(selectinload(TrainingPlan.items))
    )


def create_session(
    db: Session,
    user: User,
    training_type: TrainingType,
    recommendation_id: UUID | None = None,
    recommendation_source: str | None = None,
    recommendation_headline: str | None = None,
) -> TrainingSession:
    profile = get_patient_profile(db, user)
    if profile.current_agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")
    plan = get_or_create_today_plan(db, user)
    plan_item = next((item for item in plan.items if item.task_template.task_type == training_type), None)
    if plan_item is None:
        template = db.scalar(select(TaskTemplate).where(TaskTemplate.task_type == training_type))
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练题不存在")
        plan_item = TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=len(plan.items))
        db.add(plan_item)
        db.flush()
    recommendation = get_training_recommendation(db, user) if recommendation_source else None
    session = TrainingSession(
        patient_profile_id=profile.id,
        agent_id=profile.current_agent_id,
        training_plan_id=plan.id,
        training_type=training_type,
        recommendation_review_id=recommendation_id,
        recommendation_source=recommendation_source,
        recommendation_snapshot=build_session_recommendation_snapshot(recommendation, recommendation_headline),
        recommendation_matched=bool(recommendation and recommendation.recommended_type == training_type),
    )
    db.add(session)
    db.flush()
    db.add(
        SessionTask(
            training_session_id=session.id,
            training_plan_item_id=plan_item.id,
            task_template_id=plan_item.task_template_id,
            order_index=0,
        )
    )
    db.commit()
    return get_session(db, user, session.id)


def build_session_recommendation_snapshot(
    recommendation: TrainingRecommendationRead | None,
    recommendation_headline: str | None = None,
) -> dict | None:
    if not recommendation:
        return None
    return {
        "headline": recommendation_headline or recommendation.headline,
        "recommended_type": recommendation.recommended_type.value,
        "source": recommendation.source,
        "review_status": recommendation.review_status,
        "content_level": recommendation.content_level,
        "autonomy_level": recommendation.autonomy_level,
        "confidence": recommendation.confidence,
        "therapist_notes": recommendation.therapist_notes,
    }


def get_session(db: Session, user: User, session_id: UUID) -> TrainingSession:
    profile = get_patient_profile(db, user)
    session = db.scalar(
        select(TrainingSession)
        .where(TrainingSession.id == session_id, TrainingSession.patient_profile_id == profile.id)
        .options(selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template))
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练会话不存在")
    return session


def complete_session_if_needed(db: Session, session: TrainingSession) -> None:
    session.status = TrainingStatus.completed
    for task in session.session_tasks:
        task.status = TrainingStatus.completed
    db.commit()


def get_patient_profile_by_user_id(db: Session, patient_user_id: UUID) -> PatientProfile:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return profile
