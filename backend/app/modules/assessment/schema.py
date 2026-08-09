from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.assessment.model import AssessmentType
from app.modules.evaluations.model import EvaluationSource


LONG_TERM_METRIC_NAMES = {
    "wab_information",
    "wab_fluency",
    "wab_grammar",
    "wab_word_order",
    "wab_comprehensibility",
    "wab_repetition_comprehensibility",
    "cadl_score",
    "acceptance_score",
}


class AssessmentMetrics(BaseModel):
    wab_information: float | None = None
    wab_fluency: float | None = None
    wab_grammar: float | None = None
    wab_word_order: float | None = None
    wab_comprehensibility: float | None = None
    wab_repetition_comprehensibility: float | None = None
    cadl_score: float | None = None
    acceptance_score: float | None = None

    def compact(self) -> dict[str, float]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class AssessmentCreate(BaseModel):
    assessment_type: AssessmentType = AssessmentType.baseline
    evaluation_source: EvaluationSource = EvaluationSource.human
    assessed_at: datetime | None = None
    metrics: AssessmentMetrics
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_source_and_metrics(self) -> "AssessmentCreate":
        if self.evaluation_source == EvaluationSource.mock_ai:
            raise ValueError("阶段性量表评估不允许使用 mock_ai 作为数据来源")
        if not self.metrics.compact():
            raise ValueError("至少填写一个阶段性评估指标")
        return self


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_type: AssessmentType
    evaluation_source: EvaluationSource
    assessed_at: datetime
    metrics: dict[str, float]
    notes: str | None = None
    created_at: datetime


class MetricComparison(BaseModel):
    baseline: float | None = None
    current: float | None = None
    change: float | None = None


class AssessmentCompareRead(BaseModel):
    baseline_assessment: AssessmentRead | None = None
    current_assessment: AssessmentRead | None = None
    metrics: dict[str, MetricComparison]
