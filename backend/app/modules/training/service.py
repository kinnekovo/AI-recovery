from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.training.model import (
    SessionTask,
    TaskTemplate,
    TrainingPlan,
    TrainingPlanItem,
    TrainingSession,
    TrainingStatus,
    TrainingType,
)
from app.modules.training.schema import TaskTemplateRead, TrainingRecommendationRead
from app.modules.users.model import User
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
    from app.modules.profiles.service import refresh_ability_profile

    ability = refresh_ability_profile(db, profile.id)
    recommended_type, headline, reason, focus_points, minutes = decide_recommendation(ability)
    template = pick_template_for_recommendation(
        db,
        recommended_type=recommended_type,
        content_level=ability.current_content_level,
        autonomy_level=ability.current_autonomy_level,
    )
    return TrainingRecommendationRead(
        recommended_type=recommended_type,
        headline=headline,
        reason=reason,
        focus_points=focus_points,
        suggested_minutes=minutes,
        content_level=ability.current_content_level,
        autonomy_level=ability.current_autonomy_level,
        confidence=ability.confidence,
        profile_summary=ability.assessment_summary,
        task_template=TaskTemplateRead.model_validate(template) if template else None,
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


def create_session(db: Session, user: User, training_type: TrainingType) -> TrainingSession:
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
    session = TrainingSession(
        patient_profile_id=profile.id,
        agent_id=profile.current_agent_id,
        training_plan_id=plan.id,
        training_type=training_type,
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
