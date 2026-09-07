from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.integrations.tts.provider import get_tts_provider
from app.modules.agents.model import Agent
from app.modules.training.model import (
    RecommendationReviewStatus,
    RecommendationStrategyFeedback,
    SessionTask,
    StrategyFeedbackJudgment,
    TaskTemplate,
    TrainingPlan,
    TrainingPlanItem,
    TrainingRecommendationReview,
    TrainingSession,
    TrainingStatus,
    TrainingType,
)
from app.modules.training.recommendation_policy import (
    RECOMMENDATION_POLICY,
    analyze_trend_by_policy,
    decide_recommendation_by_policy,
    sequence_steps,
)
from app.modules.attempts.model import Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.files.service import public_url
from app.modules.files.model import FileAsset, FileType
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.consent.service import require_active_consent
from app.modules.training.schema import (
    AvatarSpeechCreate,
    AvatarSpeechRead,
    FamilyObservationRead,
    Phase3DemoStatusRead,
    RecommendationEffectRead,
    RecommendationEffectSummaryRead,
    StrategyFeedbackCreate,
    StrategyFeedbackRead,
    TaskTemplateCreate,
    TaskTemplateRead,
    TaskTemplateUpdate,
    TodayTrainingRead,
    TrainingRecommendationRead,
    TrainingRecommendationReviewUpdate,
)
from app.modules.users.model import PatientProfile, User, UserRole
from app.modules.users.service import get_patient_profile


SEED_TASKS = [
    {
        "task_type": TrainingType.repeat,
        "title": "熟悉短句：天气",
        "instruction": "请跟我说这一句。",
        "target_text": "今天天气很好。",
        "content_level": "L1",
        "autonomy_level": "S1",
        "tags": ["日常", "短句", "建立信心"],
        "recommendation_weight": 95,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "熟悉短句：喝水",
        "instruction": "请跟我说这一句。",
        "target_text": "我想喝一点温水。",
        "content_level": "L1",
        "autonomy_level": "S1",
        "tags": ["日常", "需求表达", "短句"],
        "recommendation_weight": 92,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "连贯短句：午饭",
        "instruction": "请跟我连起来说。",
        "target_text": "我今天中午想吃米饭和青菜。",
        "content_level": "L2",
        "autonomy_level": "S1",
        "tags": ["日常", "连贯", "饮食"],
        "recommendation_weight": 88,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "连贯短句：散步",
        "instruction": "请先听清楚，再完整跟读。",
        "target_text": "吃完晚饭后，我想和家人一起散步。",
        "content_level": "L3",
        "autonomy_level": "S2",
        "tags": ["家庭", "连贯", "活动"],
        "recommendation_weight": 78,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "复合短句：复诊",
        "instruction": "请尽量保持声音稳定，把句子说完整。",
        "target_text": "明天上午我要去医院复诊，请帮我准备病历。",
        "content_level": "L4",
        "autonomy_level": "S2",
        "tags": ["医疗", "复合句", "计划"],
        "recommendation_weight": 70,
    },
    {
        "task_type": TrainingType.repeat,
        "title": "挑战短句：复健安排",
        "instruction": "请完整跟读这句较长的话，注意中间不要急。",
        "target_text": "这周我想每天上午练习十分钟，下午再和家人复习一遍。",
        "content_level": "L5",
        "autonomy_level": "S3",
        "tags": ["复健", "长句", "挑战"],
        "recommendation_weight": 66,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "医院看病场景",
        "instruction": "请说说在医院看病时你想表达什么。",
        "target_text": "我想去医院看病，请医生帮我检查。",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "医院看病",
        "tags": ["医疗", "需求表达", "场景"],
        "recommendation_weight": 86,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "家庭吃饭场景",
        "instruction": "请说说吃饭时你想表达什么。",
        "target_text": "我想少吃一点米饭，多吃一些青菜。",
        "content_level": "L2",
        "autonomy_level": "S2",
        "scene_prompt": "家庭吃饭",
        "tags": ["家庭", "饮食", "场景"],
        "recommendation_weight": 84,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "外出购物场景",
        "instruction": "请说说买东西时你想表达什么。",
        "target_text": "请问这个多少钱？我想买两个苹果。",
        "content_level": "L3",
        "autonomy_level": "S3",
        "scene_prompt": "外出购物",
        "tags": ["生活", "购物", "场景"],
        "recommendation_weight": 76,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "家人沟通场景",
        "instruction": "请试着把自己的想法说给家人听。",
        "target_text": "我今天有点累，想先休息一会儿，晚点再训练。",
        "content_level": "L4",
        "autonomy_level": "S4",
        "scene_prompt": "家人沟通",
        "tags": ["家庭", "情绪", "自主表达"],
        "recommendation_weight": 72,
    },
    {
        "task_type": TrainingType.scenario,
        "title": "社区问路场景",
        "instruction": "请围绕问路场景说清楚自己的需求。",
        "target_text": "请问去社区卫生服务中心怎么走？我想坐电梯上去。",
        "content_level": "L5",
        "autonomy_level": "S4",
        "scene_prompt": "社区问路",
        "tags": ["社区", "问路", "自主表达"],
        "recommendation_weight": 64,
    },
]


def ensure_seed_tasks(db: Session) -> None:
    existing = {item.title: item for item in db.scalars(select(TaskTemplate))}
    changed = False
    for item in SEED_TASKS:
        template = existing.get(item["title"])
        if template:
            for field in [
                "task_type",
                "instruction",
                "target_text",
                "content_level",
                "autonomy_level",
                "scene_prompt",
                "tags",
                "recommendation_weight",
            ]:
                if field in item and getattr(template, field) != item[field]:
                    setattr(template, field, item[field])
                    changed = True
            if not template.is_active:
                template.is_active = True
                changed = True
            continue
        db.add(TaskTemplate(**item, scoring_config={"mode": "mock"}))
        changed = True
    legacy = existing.get("短句跟读")
    if legacy and legacy.is_active:
        legacy.is_active = False
        changed = True
    if changed:
        db.commit()


def get_training_types() -> list[str]:
    return [TrainingType.repeat.value, TrainingType.scenario.value]


def list_task_templates(
    db: Session,
    training_type: TrainingType | None = None,
    include_inactive: bool = False,
) -> list[TaskTemplateRead]:
    ensure_seed_tasks(db)
    stmt = select(TaskTemplate).order_by(
        TaskTemplate.task_type.asc(),
        TaskTemplate.content_level.asc(),
        TaskTemplate.autonomy_level.asc(),
        TaskTemplate.recommendation_weight.desc(),
    )
    if training_type:
        stmt = stmt.where(TaskTemplate.task_type == training_type)
    if not include_inactive:
        stmt = stmt.where(TaskTemplate.is_active.is_(True))
    return [TaskTemplateRead.model_validate(item) for item in db.scalars(stmt)]


def create_task_template(db: Session, payload: TaskTemplateCreate) -> TaskTemplateRead:
    template = TaskTemplate(
        task_type=payload.task_type,
        title=payload.title.strip(),
        instruction=payload.instruction.strip(),
        target_text=payload.target_text.strip(),
        content_level=payload.content_level.strip() or "L1",
        autonomy_level=payload.autonomy_level.strip() or "S1",
        scene_prompt=payload.scene_prompt.strip() if payload.scene_prompt else None,
        tags=[item.strip() for item in payload.tags if item.strip()],
        recommendation_weight=max(0, min(payload.recommendation_weight, 100)),
        is_active=payload.is_active,
        scoring_config={"mode": "mock"},
    )
    if not template.title or not template.instruction or not template.target_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练材料标题、说明和文本不能为空")
    db.add(template)
    db.commit()
    db.refresh(template)
    return TaskTemplateRead.model_validate(template)


def update_task_template(db: Session, template_id: UUID, payload: TaskTemplateUpdate) -> TaskTemplateRead:
    template = db.get(TaskTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练材料不存在")
    for field in ["title", "instruction", "target_text", "content_level", "autonomy_level", "scene_prompt"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(template, field, value.strip() if isinstance(value, str) else value)
    if payload.tags is not None:
        template.tags = [item.strip() for item in payload.tags if item.strip()]
    if payload.recommendation_weight is not None:
        template.recommendation_weight = max(0, min(payload.recommendation_weight, 100))
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if not template.title or not template.instruction or not template.target_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练材料标题、说明和文本不能为空")
    db.commit()
    db.refresh(template)
    return TaskTemplateRead.model_validate(template)


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
    recent_effects = recent_recommendation_effects_by_profile(db, patient_profile_id)
    completed_effects = [effect for effect in reversed(recent_effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    trend = analyze_trend_by_policy(completed_effects)
    decision = decide_recommendation_by_policy(ability, trend)
    manual_note = latest_recommendation_note(db, patient_profile_id)
    system_recommendation = build_recommendation_read(
        db=db,
        recommended_type=decision.recommended_type,
        headline=decision.headline,
        reason=decision.reason,
        focus_points=decision.focus_points,
        suggested_minutes=decision.suggested_minutes,
        content_level=decision.content_level,
        autonomy_level=decision.autonomy_level,
        confidence=ability.confidence,
        profile_summary=ability.assessment_summary,
        source="system",
        review_status=RecommendationReviewStatus.pending_review.value,
        therapist_notes=manual_note.next_strategy if manual_note else None,
        updated_at=manual_note.created_at if manual_note else None,
        adaptation_note=decision.adaptation_note,
        reminder=trend.patient_reminder,
    )
    return system_recommendation


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
    effects = recent_recommendation_effects_by_profile(db, profile.id)
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
        attribution_points=trend["attribution_points"],
        reminder_level=trend["reminder_level"],
        patient_reminder=trend["patient_reminder"],
        family_reminder=trend["family_reminder"],
        therapist_reminder=trend["therapist_reminder"],
        latest=effects,
    )


def recent_recommendation_effects_by_profile(db: Session, patient_profile_id: UUID) -> list[RecommendationEffectRead]:
    sessions = list(
        db.scalars(
            select(TrainingSession)
            .where(
                TrainingSession.patient_profile_id == patient_profile_id,
                TrainingSession.recommendation_source.is_not(None),
            )
            .order_by(TrainingSession.created_at.desc())
            .limit(8)
        )
    )
    return [build_recommendation_effect(db, session) for session in sessions]


def create_strategy_feedback(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    payload: StrategyFeedbackCreate,
) -> StrategyFeedbackRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    effects = get_patient_recommendation_effects(db, patient_user_id)
    try:
        judgment = StrategyFeedbackJudgment(payload.judgment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="策略反馈判断无效") from exc
    feedback = RecommendationStrategyFeedback(
        patient_profile_id=profile.id,
        therapist_user_id=therapist.id,
        trend_status=effects.trend_status,
        judgment=judgment,
        reason=payload.reason,
        next_strategy=payload.next_strategy,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return StrategyFeedbackRead.model_validate(feedback)


def latest_strategy_feedback(db: Session, patient_profile_id: UUID) -> RecommendationStrategyFeedback | None:
    return db.scalar(
        select(RecommendationStrategyFeedback)
        .where(RecommendationStrategyFeedback.patient_profile_id == patient_profile_id)
        .order_by(RecommendationStrategyFeedback.created_at.desc())
    )


def latest_recommendation_note(db: Session, patient_profile_id: UUID) -> RecommendationStrategyFeedback | None:
    return db.scalar(
        select(RecommendationStrategyFeedback)
        .where(
            RecommendationStrategyFeedback.patient_profile_id == patient_profile_id,
            RecommendationStrategyFeedback.trend_status == "manual_note",
        )
        .order_by(RecommendationStrategyFeedback.created_at.desc())
    )


def get_family_observation(db: Session) -> FamilyObservationRead:
    patient = first_patient(db)
    if not patient:
        return FamilyObservationRead(
            patient_username="暂无患者",
            training_count=0,
            completed_recommended_sessions=0,
            recommendation_headline="暂无训练建议",
            recommendation_source="system",
            trend_summary="还没有可观察的训练记录。",
            strategy_hint="请等待患者完成训练后再查看。",
            therapist_note=None,
            reminder_level="info",
            family_reminder="患者完成训练后，这里会显示陪伴提醒。",
            current_level_label="等待开始",
            progress_label="暂无趋势",
        progress_percent=0,
        level_items=family_empty_level_items(),
        trend_items=[],
        recent_records=[],
    )
    return build_family_observation_for_patient(db, patient.id)


def build_family_observation_for_patient(
    db: Session,
    patient_user_id: UUID,
    bound_patients: list[dict] | None = None,
) -> FamilyObservationRead:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = get_patient_profile_by_user_id(db, patient.id)
    recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=True)
    effects = get_patient_recommendation_effects(db, patient.id)
    feedback = latest_strategy_feedback(db, profile.id)
    training_count = db.scalar(select(func.count(TrainingSession.id)).where(TrainingSession.patient_profile_id == profile.id))
    last_training_at = latest_training_at(db, profile.id)
    family_visuals = build_family_visuals(effects)
    return FamilyObservationRead(
        patient_username=patient.username,
        training_count=training_count or 0,
        completed_recommended_sessions=effects.completed_recommended_sessions,
        last_training_at=last_training_at,
        adherence_summary=family_adherence_summary(training_count or 0, effects.completed_recommended_sessions, last_training_at),
        recommendation_headline=recommendation.headline,
        recommendation_source=recommendation.source,
        trend_summary=effects.trend_summary,
        strategy_hint=feedback.next_strategy if feedback and feedback.next_strategy else effects.family_reminder or effects.strategy_hint,
        therapist_note=feedback.reason if feedback and feedback.reason else recommendation.therapist_notes,
        reminder_level=effects.reminder_level,
        family_reminder=effects.family_reminder,
        current_level_label=family_visuals["current_level_label"],
        progress_label=family_visuals["progress_label"],
        progress_percent=family_visuals["progress_percent"],
        level_items=family_visuals["level_items"],
        trend_items=family_visuals["trend_items"],
        recent_records=family_recent_training_records(db, profile.id),
        bound_patients=bound_patients or [],
        selected_patient_user_id=patient.id,
    )


def latest_training_at(db: Session, patient_profile_id: UUID):
    return db.scalar(
        select(func.max(Attempt.created_at))
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(TrainingSession.patient_profile_id == patient_profile_id)
    )


def family_adherence_summary(training_count: int, completed_recommended_sessions: int, last_training_at) -> str:
    if training_count <= 0:
        return "还没有训练记录，可以先陪他完成一次短句练习。"
    if completed_recommended_sessions <= 0:
        return f"已经练了 {training_count} 次，但还没有完成建议训练，可以先陪他按今日建议完成一组。"
    if last_training_at:
        return f"已经练了 {training_count} 次，其中 {completed_recommended_sessions} 次完成建议训练，最近一次在 {last_training_at.strftime('%m月%d日')}。"
    return f"已经练了 {training_count} 次，其中 {completed_recommended_sessions} 次完成建议训练。"


def build_family_visuals(effects: RecommendationEffectSummaryRead) -> dict:
    latest = effects.latest[0] if effects.latest else None
    metrics = latest.metrics if latest else {}
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    speech_rate = metrics.get("speech_rate")
    loudness = metrics.get("loudness")
    progress_percent = family_progress_percent(accuracy, errors)
    return {
        "current_level_label": family_level_label(progress_percent, effects.completed_recommended_sessions),
        "progress_label": family_progress_label(effects.trend_status),
        "progress_percent": progress_percent,
        "level_items": [
            {
                "key": "expression",
                "label": "表达完整度",
                "icon": "message-circle",
                "value": family_value_label(accuracy, "%"),
                "level": progress_percent,
                "tone": family_tone_from_percent(progress_percent),
                "hint": "能不能把一句话比较完整地说出来。",
            },
            {
                "key": "stability",
                "label": "稳定度",
                "icon": "shield-check",
                "value": "较稳" if errors is not None and errors <= 1 else "需陪伴" if errors is not None else "观察中",
                "level": family_stability_percent(errors),
                "tone": family_tone_from_percent(family_stability_percent(errors)),
                "hint": "错误和停顿越少，说明练习越稳定。",
            },
            {
                "key": "rhythm",
                "label": "说话节奏",
                "icon": "audio-lines",
                "value": family_rhythm_label(speech_rate),
                "level": family_rhythm_percent(speech_rate),
                "tone": family_tone_from_percent(family_rhythm_percent(speech_rate)),
                "hint": "不是越快越好，平稳、能听清更重要。",
            },
            {
                "key": "voice",
                "label": "声音状态",
                "icon": "volume-2",
                "value": family_voice_label(loudness),
                "level": family_voice_percent(loudness),
                "tone": family_tone_from_percent(family_voice_percent(loudness)),
                "hint": "声音保持自然、清楚即可。",
            },
        ],
        "trend_items": family_trend_items(effects.latest),
    }


def family_empty_level_items() -> list[dict]:
    return [
        {"key": "expression", "label": "表达完整度", "icon": "message-circle", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "stability", "label": "稳定度", "icon": "shield-check", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "rhythm", "label": "说话节奏", "icon": "audio-lines", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
        {"key": "voice", "label": "声音状态", "icon": "volume-2", "value": "待训练", "level": 0, "tone": "muted", "hint": "完成训练后自动显示。"},
    ]


def family_progress_percent(accuracy: float | None, errors: float | None) -> int:
    if accuracy is None:
        return 0
    score = accuracy
    if errors is not None:
        score -= min(max(errors - 1, 0), 5) * 4
    return int(max(0, min(round(score), 100)))


def family_level_label(percent: int, completed_count: int) -> str:
    if completed_count == 0:
        return "正在建立记录"
    if percent >= 90:
        return "表现稳定"
    if percent >= 75:
        return "稳步练习中"
    if percent >= 55:
        return "需要多陪伴"
    return "先建立信心"


def family_progress_label(status: str) -> str:
    if status == "effective":
        return "正在进步"
    if status == "needs_adjustment":
        return "需要调整"
    if status == "mixed":
        return "有波动"
    return "继续观察"


def family_value_label(value: float | None, unit: str) -> str:
    if value is None:
        return "观察中"
    return f"{value:g}{unit}"


def family_tone_from_percent(percent: int) -> str:
    if percent >= 85:
        return "good"
    if percent >= 65:
        return "steady"
    if percent > 0:
        return "watch"
    return "muted"


def family_stability_percent(errors: float | None) -> int:
    if errors is None:
        return 0
    return int(max(20, min(100, 100 - errors * 18)))


def family_rhythm_percent(speech_rate: float | None) -> int:
    if speech_rate is None:
        return 0
    return int(max(25, min(100, 100 - abs(speech_rate - 210) * 0.7)))


def family_voice_percent(loudness: float | None) -> int:
    if loudness is None:
        return 0
    return int(max(25, min(100, 100 - abs(loudness - 69) * 3)))


def family_rhythm_label(speech_rate: float | None) -> str:
    if speech_rate is None:
        return "观察中"
    if speech_rate < 180:
        return "偏慢"
    if speech_rate > 240:
        return "偏快"
    return "平稳"


def family_voice_label(loudness: float | None) -> str:
    if loudness is None:
        return "观察中"
    if loudness < 60:
        return "偏轻"
    if loudness > 78:
        return "偏响"
    return "清楚"


def family_trend_items(effects: list[RecommendationEffectRead]) -> list[dict]:
    completed = [effect for effect in reversed(effects) if effect.status == TrainingStatus.completed.value and effect.metrics]
    if not completed:
        return []
    recent = completed[-4:]
    items = []
    for index, effect in enumerate(recent, start=1):
        percent = family_progress_percent(effect.metrics.get("script_accuracy"), effect.metrics.get("error_count"))
        items.append(
            {
                "label": f"第 {index} 次",
                "value": percent,
                "summary": effect.summary,
                "created_at": effect.created_at.isoformat(),
            }
        )
    return items


def family_recent_training_records(db: Session, patient_profile_id: UUID, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(Attempt, TrainingSession, SessionTask, AttemptAnalysisResult)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(AttemptAnalysisResult, AttemptAnalysisResult.attempt_id == Attempt.id)
        .where(TrainingSession.patient_profile_id == patient_profile_id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    ).all()
    records = []
    for attempt, session, task, analysis in rows:
        metrics = attempt_process_metrics(db, attempt.id)
        records.append(
            {
                "attempt_id": str(attempt.id),
                "created_at": attempt.created_at.isoformat(),
                "training_type": session.training_type.value,
                "task_title": task.task_template.title,
                "target_text": task.task_template.target_text,
                "audio_url": public_url(attempt.audio_file) if attempt.audio_file else None,
                "asr_text": analysis.asr_text if analysis else None,
                "summary": family_record_summary(metrics, attempt.analysis_status.value),
                "metrics": metrics,
            }
        )
    return records


def attempt_process_metrics(db: Session, attempt_id: UUID) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .where(
            AttemptEvaluation.attempt_id == attempt_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
    ).all()
    return {name: round(float(value), 1) for name, value in rows}


def family_record_summary(metrics: dict[str, float], status: str) -> str:
    if status != TrainingStatus.completed.value:
        return "这次训练还没有完成分析。"
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    if accuracy is None:
        return "这次训练已保存，暂时没有完整评分。"
    if accuracy >= 90 and (errors is None or errors <= 1):
        return "这次表达比较完整，状态较稳定。"
    if accuracy >= 70:
        return "这次能完成主要内容，可以继续陪伴巩固。"
    return "这次有些地方没有说完整，陪伴时可以先练短句。"


def get_phase3_demo_status(db: Session) -> Phase3DemoStatusRead:
    patient = first_patient(db)
    if not patient:
        return Phase3DemoStatusRead(
            has_patient=False,
            has_recommendation=False,
            has_therapist_review=False,
            has_recommended_training=False,
            has_effect_trend=False,
            has_strategy_feedback=False,
            next_step="先创建或准备一个患者账号。",
        )
    profile = get_patient_profile_by_user_id(db, patient.id)
    recommendation = get_patient_training_recommendation(db, profile.id, include_review_override=True)
    review = latest_recommendation_review(db, profile.id)
    effects = get_patient_recommendation_effects(db, patient.id)
    feedback = latest_strategy_feedback(db, profile.id)
    has_effect_trend = effects.completed_recommended_sessions >= 1
    return Phase3DemoStatusRead(
        has_patient=True,
        has_recommendation=bool(recommendation.headline),
        has_therapist_review=bool(review and review.review_status in {RecommendationReviewStatus.confirmed, RecommendationReviewStatus.adjusted}),
        has_recommended_training=effects.total_recommended_sessions > 0,
        has_effect_trend=has_effect_trend,
        has_strategy_feedback=feedback is not None,
        next_step=phase3_next_step(review, effects, feedback),
    )


def first_patient(db: Session) -> User | None:
    return db.scalar(select(User).where(User.role == UserRole.patient).order_by(User.created_at.asc()))


def phase3_next_step(
    review: TrainingRecommendationReview | None,
    effects: RecommendationEffectSummaryRead,
    feedback: RecommendationStrategyFeedback | None,
) -> str:
    if not review:
        return "治疗师复核一次训练推荐。"
    if effects.total_recommended_sessions == 0:
        return "患者从推荐入口完成一次训练。"
    if effects.completed_recommended_sessions == 0:
        return "患者上传录音并生成反馈。"
    if not feedback:
        return "治疗师记录一次策略反馈。"
    return "Phase 3 演示闭环已打通。"


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
    result = analyze_trend_by_policy(completed)
    return {
        "status": result.status,
        "summary": result.summary,
        "hint": result.hint,
        "evidence": result.evidence,
        "attribution_points": result.attribution_points,
        "reminder_level": result.reminder_level,
        "patient_reminder": result.patient_reminder,
        "family_reminder": result.family_reminder,
        "therapist_reminder": result.therapist_reminder,
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
    adaptation_note: str | None = None,
    reminder: str | None = None,
) -> TrainingRecommendationRead:
    template = pick_template_for_recommendation(
        db,
        recommended_type=recommended_type,
        content_level=content_level,
        autonomy_level=autonomy_level,
    )
    sequence = pick_task_sequence_for_recommendation(
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
        task_sequence=[TaskTemplateRead.model_validate(item) for item in sequence],
        policy_version=RECOMMENDATION_POLICY["version"],
        adaptation_note=adaptation_note,
        reminder=reminder,
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
    templates = list(
        db.scalars(
            select(TaskTemplate).where(
                TaskTemplate.task_type == recommended_type,
                TaskTemplate.is_active.is_(True),
            )
        )
    )
    if not templates:
        return None
    return min(
        templates,
        key=lambda template: (
            abs(level_number(template.content_level) - level_number(content_level)),
            abs(level_number(template.autonomy_level) - level_number(autonomy_level)),
            -template.recommendation_weight,
            template.created_at,
        ),
    )


def pick_task_sequence_for_recommendation(
    db: Session,
    recommended_type: TrainingType,
    content_level: str,
    autonomy_level: str,
) -> list[TaskTemplate]:
    content = level_number(content_level)
    autonomy = level_number(autonomy_level)
    candidates = list(
        db.scalars(
            select(TaskTemplate)
            .where(TaskTemplate.is_active.is_(True))
            .order_by(TaskTemplate.recommendation_weight.desc(), TaskTemplate.created_at.asc())
        )
    )
    if not candidates:
        return []

    steps = []
    for step in sequence_steps():
        step_type = TrainingType.repeat if step["type"] == "repeat" else recommended_type
        steps.append(
            (
                step["label"],
                step_type,
                max(1, min(5, content + step["content_delta"])),
                max(1, min(4, autonomy + step["autonomy_delta"])),
                bool(step.get("not_easier")),
            )
        )
    selected: list[TaskTemplate] = []
    used_ids = set()
    for _label, step_type, step_content, step_autonomy, not_easier in steps:
        pool = [item for item in candidates if item.task_type == step_type and item.id not in used_ids]
        if not_easier:
            harder_pool = [
                item
                for item in pool
                if level_number(item.content_level) >= content
                and level_number(item.autonomy_level) >= max(1, autonomy - 1)
            ]
            if harder_pool:
                pool = harder_pool
        if not pool:
            pool = [item for item in candidates if item.id not in used_ids]
        if not pool:
            break
        best = min(
            pool,
            key=lambda template: (
                abs(level_number(template.content_level) - step_content),
                abs(level_number(template.autonomy_level) - step_autonomy),
                -template.recommendation_weight,
                template.created_at,
            ),
        )
        selected.append(best)
        used_ids.add(best.id)
    return selected


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
    templates = list(
        db.scalars(
            select(TaskTemplate)
            .where(TaskTemplate.is_active.is_(True))
            .order_by(TaskTemplate.task_type.asc(), TaskTemplate.content_level.asc(), TaskTemplate.recommendation_weight.desc())
        )
    )
    for index, template in enumerate(templates):
        db.add(TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=index))
    db.commit()
    return db.scalar(
        select(TrainingPlan).where(TrainingPlan.id == plan.id).options(selectinload(TrainingPlan.items))
    )


def get_today_training(db: Session, user: User) -> TodayTrainingRead:
    plan = get_or_create_today_plan(db, user)
    completed_recommended_sessions = db.scalar(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.training_plan_id == plan.id,
            TrainingSession.recommendation_source.is_not(None),
            TrainingSession.status == TrainingStatus.completed,
        )
    )
    return TodayTrainingRead(
        plan_id=plan.id,
        title=plan.title,
        status=TrainingStatus.completed.value if completed_recommended_sessions else plan.status.value,
        items_count=len(plan.items),
        recommended_completed=bool(completed_recommended_sessions),
        completed_recommended_sessions=completed_recommended_sessions or 0,
    )


def create_session(
    db: Session,
    user: User,
    training_type: TrainingType,
    recommendation_id: UUID | None = None,
    recommendation_source: str | None = None,
    recommendation_headline: str | None = None,
    recommendation_task_ids: list[UUID] | None = None,
) -> TrainingSession:
    profile = get_patient_profile(db, user)
    if profile.current_agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")
    recommendation = get_training_recommendation(db, user) if recommendation_source else None
    recommended_template = recommendation.task_template if recommendation else None
    recommended_task_ids = recommendation_task_ids or [item.id for item in (recommendation.task_sequence if recommendation else [])]
    plan = get_or_create_today_plan(db, user)
    plan_item = None
    if recommended_template and recommendation and recommendation.recommended_type == training_type:
        plan_item = next((item for item in plan.items if item.task_template_id == recommended_template.id), None)
    if plan_item is None:
        plan_item = next((item for item in plan.items if item.task_template.task_type == training_type), None)
    if plan_item is None:
        template = db.scalar(
            select(TaskTemplate)
            .where(TaskTemplate.task_type == training_type, TaskTemplate.is_active.is_(True))
            .order_by(TaskTemplate.recommendation_weight.desc(), TaskTemplate.created_at.asc())
        )
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练题不存在")
        plan_item = TrainingPlanItem(training_plan_id=plan.id, task_template_id=template.id, order_index=len(plan.items))
        db.add(plan_item)
        db.flush()
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
    session_plan_items = []
    if recommendation_source and recommended_task_ids:
        for index, task_template_id in enumerate(recommended_task_ids):
            template = db.get(TaskTemplate, task_template_id)
            if not template or not template.is_active:
                continue
            existing_plan_item = next((item for item in plan.items if item.task_template_id == template.id), None)
            if existing_plan_item is None:
                existing_plan_item = TrainingPlanItem(
                    training_plan_id=plan.id,
                    task_template_id=template.id,
                    order_index=len(plan.items) + len(session_plan_items),
                )
                db.add(existing_plan_item)
                db.flush()
            session_plan_items.append(existing_plan_item)
    if not session_plan_items:
        session_plan_items = [plan_item]

    for index, item in enumerate(session_plan_items):
        db.add(
            SessionTask(
                training_session_id=session.id,
                training_plan_item_id=item.id,
                task_template_id=item.task_template_id,
                order_index=index,
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
        "task_sequence": [str(item.id) for item in recommendation.task_sequence],
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


def create_avatar_speech(db: Session, user: User, payload: AvatarSpeechCreate) -> AvatarSpeechRead:
    text = payload.text.strip()
    scene = payload.scene.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本不能为空")
    if len(text) > 160:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本过长")
    if not scene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播场景不能为空")

    profile = get_patient_profile(db, user)
    if profile.current_agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")
    agent = db.get(Agent, profile.current_agent_id)
    if not agent or agent.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先创建并选择智能体")

    session = None
    if payload.session_id:
        session = get_session(db, user, payload.session_id)
    if payload.session_task_id:
        task = db.scalar(
            select(SessionTask)
            .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
            .where(SessionTask.id == payload.session_task_id, TrainingSession.patient_profile_id == profile.id)
        )
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练任务不存在")
        if session and task.training_session_id != session.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="训练任务不属于当前会话")

    provider = get_tts_provider()
    fallback = agent.voice_external_id is None
    if agent.voice_external_id:
        require_active_consent(db, user, agent.id, "voice")
    audio_path = provider.synthesize(text, agent.voice_external_id or "default")
    path = Path(audio_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="数字人口播音频生成失败")
    asset = FileAsset(
        owner_user_id=user.id,
        file_type=FileType.generated_audio,
        original_name=path.name,
        storage_path=str(path),
        mime_type="audio/wav",
        size_bytes=path.stat().st_size,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return AvatarSpeechRead(
        text=text,
        audio_file_id=asset.id,
        audio_url=public_url(asset),
        provider=provider.name,
        fallback=fallback,
    )


def complete_session_if_needed(db: Session, session: TrainingSession) -> None:
    if all(task.status == TrainingStatus.completed for task in session.session_tasks):
        session.status = TrainingStatus.completed
    db.commit()


def get_patient_profile_by_user_id(db: Session, patient_user_id: UUID) -> PatientProfile:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return profile
