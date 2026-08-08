from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.attempts.service import get_attempt
from app.modules.evaluations.model import (
    AttemptEvaluation,
    EvaluationMetric,
    EvaluationMetricCategory,
    EvaluationSource,
)
from app.modules.evaluations.schema import (
    AttemptEvaluationBatchCreate,
    AttemptEvaluationBatchRead,
    AttemptEvaluationRead,
)
from app.modules.users.model import User


DEFAULT_METRICS = [
    {
        "name": "script_accuracy",
        "category": EvaluationMetricCategory.process,
        "description": "正确发音字数 / 脚本总字数，用于衡量脚本输出完整性。",
        "unit": "%",
        "normal_range": {"target": 100, "operator": ">="},
    },
    {
        "name": "error_count",
        "category": EvaluationMetricCategory.process,
        "description": "无意义重复、超过3秒停顿、难以理解发音和插入语的总次数。",
        "unit": "次",
        "normal_range": {"target": 0, "operator": "=="},
    },
    {
        "name": "speech_rate",
        "category": EvaluationMetricCategory.process,
        "description": "有效交流字数 / 说话时间。",
        "unit": "字/min",
        "normal_range": {"min": 180, "max": 240},
    },
    {
        "name": "loudness",
        "category": EvaluationMetricCategory.process,
        "description": "训练录音的平均响度。",
        "unit": "dBA",
        "normal_range": {"min": 60, "max": 78},
    },
    {
        "name": "wab_information",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 自发言语信息量。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "wab_fluency",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 自发言语流利性。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "wab_grammar",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 自发言语语法能力。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "wab_word_order",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 自发言语语序。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "wab_comprehensibility",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 自发言语可懂度。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "wab_repetition_comprehensibility",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "WAB 复述可懂度。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "cadl_score",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "CADL 日常交流能力评分。",
        "unit": "分",
        "normal_range": {},
    },
    {
        "name": "acceptance_score",
        "category": EvaluationMetricCategory.long_term_effect,
        "description": "患者或家属对训练方式、智能体和交互流程的接受度。",
        "unit": "分",
        "normal_range": {},
    },
]


def ensure_default_metrics(db: Session) -> None:
    existing_names = set(db.scalars(select(EvaluationMetric.name)))
    changed = False
    for metric in DEFAULT_METRICS:
        if metric["name"] in existing_names:
            continue
        db.add(EvaluationMetric(**metric))
        changed = True
    if changed:
        db.commit()


def list_metrics(db: Session, category: EvaluationMetricCategory | None = None) -> list[EvaluationMetric]:
    ensure_default_metrics(db)
    stmt = select(EvaluationMetric).order_by(EvaluationMetric.category, EvaluationMetric.name)
    if category:
        stmt = stmt.where(EvaluationMetric.category == category)
    return list(db.scalars(stmt))


def _get_metric(db: Session, metric_id: UUID | None, metric_name: str | None) -> EvaluationMetric:
    if metric_id:
        metric = db.get(EvaluationMetric, metric_id)
    else:
        metric = db.scalar(select(EvaluationMetric).where(EvaluationMetric.name == metric_name))
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评价指标不存在")
    return metric


def list_attempt_evaluations(db: Session, user: User, attempt_id: UUID) -> AttemptEvaluationBatchRead:
    attempt = get_attempt(db, user, attempt_id)
    rows = list(
        db.scalars(
            select(AttemptEvaluation)
            .where(AttemptEvaluation.attempt_id == attempt.id)
            .options(selectinload(AttemptEvaluation.metric))
            .order_by(AttemptEvaluation.created_at.asc())
        )
    )
    return AttemptEvaluationBatchRead(attempt_id=attempt.id, items=[to_read(row) for row in rows])


def save_attempt_evaluations(
    db: Session,
    user: User,
    attempt_id: UUID,
    payload: AttemptEvaluationBatchCreate,
) -> AttemptEvaluationBatchRead:
    ensure_default_metrics(db)
    attempt = get_attempt(db, user, attempt_id)
    saved: list[AttemptEvaluation] = []
    for item in payload.items:
        metric = _get_metric(db, item.metric_id, item.metric_name)
        evaluation = db.scalar(
            select(AttemptEvaluation).where(
                AttemptEvaluation.attempt_id == attempt.id,
                AttemptEvaluation.metric_id == metric.id,
                AttemptEvaluation.evaluation_source == item.evaluation_source,
            )
        )
        if evaluation:
            evaluation.value = item.value
        else:
            evaluation = AttemptEvaluation(
                attempt_id=attempt.id,
                metric_id=metric.id,
                value=item.value,
                evaluation_source=item.evaluation_source,
            )
            db.add(evaluation)
        saved.append(evaluation)
    db.commit()
    for item in saved:
        db.refresh(item, attribute_names=["metric"])
    return AttemptEvaluationBatchRead(attempt_id=attempt.id, items=[to_read(item) for item in saved])


def to_read(evaluation: AttemptEvaluation) -> AttemptEvaluationRead:
    return AttemptEvaluationRead(
        id=evaluation.id,
        attempt_id=evaluation.attempt_id,
        metric_id=evaluation.metric_id,
        metric_name=evaluation.metric.name,
        metric_category=evaluation.metric.category,
        value=evaluation.value,
        evaluation_source=evaluation.evaluation_source,
        created_at=evaluation.created_at,
    )
