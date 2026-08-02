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
