from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.evaluations.model import EvaluationMetricCategory, EvaluationSource


class EvaluationMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: EvaluationMetricCategory
    description: str
    unit: str | None = None
    normal_range: dict[str, Any]
    created_at: datetime


class AttemptEvaluationItemCreate(BaseModel):
    metric_id: UUID | None = None
    metric_name: str | None = None
    value: float
    evaluation_source: EvaluationSource = EvaluationSource.human

    @model_validator(mode="after")
    def validate_metric_reference(self) -> "AttemptEvaluationItemCreate":
        if not self.metric_id and not self.metric_name:
            raise ValueError("metric_id 或 metric_name 至少提供一个")
        return self


class AttemptEvaluationBatchCreate(BaseModel):
    items: list[AttemptEvaluationItemCreate] = Field(min_length=1)


class AttemptEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_id: UUID
    metric_id: UUID
    metric_name: str
    metric_category: EvaluationMetricCategory
    value: float
    evaluation_source: EvaluationSource
    created_at: datetime


class AttemptEvaluationBatchRead(BaseModel):
    attempt_id: UUID
    items: list[AttemptEvaluationRead]


class ProcessEvaluation(BaseModel):
    script_accuracy: float
    error_count: int
    speech_rate: float
    loudness: float
    details: dict[str, Any] = Field(default_factory=dict)
