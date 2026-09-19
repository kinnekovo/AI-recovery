from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.assessment.model import AssessmentReviewStatus, AssessmentType
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

PROCESS_METRIC_NAMES = {
    "script_accuracy",
    "error_count",
    "speech_rate",
    "loudness",
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
    instrument_name: str | None = None
    instrument_version: str | None = None
    language_locale: str | None = None
    localization_version: str | None = None
    assessment_stage: str | None = None
    raw_item_results: dict = Field(default_factory=dict)
    subscale_results: dict = Field(default_factory=dict)
    total_result: dict = Field(default_factory=dict)
    missing_items: list[str] = Field(default_factory=list)
    score_unit: str | None = None
    administration_mode: str | None = None
    device_and_environment: dict = Field(default_factory=dict)
    duration_seconds: int | None = None
    protocol_deviations: dict = Field(default_factory=dict)
    protocol_deviation_reasons: list[str] = Field(default_factory=list)

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
    patient_profile_id: UUID
    source_attempt_id: UUID | None = None
    assessment_type: AssessmentType
    evaluation_source: EvaluationSource
    review_status: AssessmentReviewStatus
    reviewed_by_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    assessed_at: datetime
    metrics: dict[str, float]
    notes: str | None = None
    therapist_notes: str | None = None
    source_audio_url: str | None = None
    source_asr_text: str | None = None
    source_target_text: str | None = None
    source_process_details: dict | None = None
    created_at: datetime
    instrument_name: str | None = None
    instrument_version: str | None = None
    language_locale: str | None = None
    localization_version: str | None = None
    assessment_stage: str | None = None
    raw_item_results: dict = Field(default_factory=dict)
    subscale_results: dict = Field(default_factory=dict)
    total_result: dict = Field(default_factory=dict)
    missing_items: list = Field(default_factory=list)
    score_unit: str | None = None
    administration_mode: str | None = None


class AssessmentReviewUpdate(BaseModel):
    review_status: AssessmentReviewStatus = AssessmentReviewStatus.confirmed
    metrics: dict[str, float] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    therapist_notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_review(self) -> "AssessmentReviewUpdate":
        if self.review_status not in {AssessmentReviewStatus.confirmed, AssessmentReviewStatus.adjusted}:
            raise ValueError("治疗师只能确认或修正自动评估记录")
        if self.review_status == AssessmentReviewStatus.adjusted and self.metrics is None and self.notes is None:
            raise ValueError("修正评估时至少需要调整指标或备注")
        return self


class ClinicalSourceUpdate(BaseModel):
    """Professional source fields only; canonical data is deliberately absent."""
    instrument_name: str | None = None
    instrument_version: str | None = None
    language_locale: str | None = None
    localization_version: str | None = None
    raw_item_results: dict | None = None
    subscale_results: dict | None = None
    total_result: dict | None = None
    missing_items: list[str] | None = None
    score_unit: str | None = None
    administration_mode: str | None = None
    device_and_environment: dict | None = None
    protocol_deviations: dict | None = None
    protocol_deviation_reasons: list[str] | None = None
    revision_reason: str | None = Field(default=None, max_length=1000)


class MetricComparison(BaseModel):
    baseline: float | None = None
    current: float | None = None
    change: float | None = None


class AssessmentCompareRead(BaseModel):
    baseline_assessment: AssessmentRead | None = None
    current_assessment: AssessmentRead | None = None
    metrics: dict[str, MetricComparison]
