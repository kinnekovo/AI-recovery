from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputProvenanceSnapshot(BaseModel):
    """Immutable input/provider/contract record; no generic confidence field."""

    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    providers: dict[str, Any] = Field(default_factory=dict)
    contract_version: str | None = None
    device_context: dict[str, Any] = Field(default_factory=dict)


class QualityGateSnapshot(BaseModel):
    """Carries the R0 evidence-gate decision without duplicating its logic."""

    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    loudness_unit: str | None = None
    algorithm_version: str | None = None
    audio_quality: str | None = None
    measurement_quality: str | None = None


class EvaluationDimensionResultCreate(BaseModel):
    dimension_code: str = Field(min_length=1, max_length=100)
    value: float | None = None
    level: str | None = Field(default=None, max_length=80)
    unit: str | None = Field(default=None, max_length=40)
    status: Literal["measured", "not_observed", "unavailable", "not_applicable"]
    measurement_quality: dict[str, Any] = Field(default_factory=dict)
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def measured_requires_a_value_or_level(self):
        if self.status == "measured" and self.value is None and self.level is None:
            raise ValueError("measured dimension requires value or level")
        if self.status != "measured" and self.value is not None:
            raise ValueError("non-measured dimension value must be null")
        return self


class EvaluationRunCreate(BaseModel):
    patient_profile_id: UUID
    domain: Literal["repeat", "functional_communication", "clinical_stage"]
    source_type: Literal["attempt", "dialogue_session", "assessment_session"]
    source_id: UUID
    algorithm_version: str = Field(min_length=1, max_length=120)
    input_fingerprint: str | None = Field(default=None, max_length=64)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    input_provenance: InputProvenanceSnapshot
    quality_gate: QualityGateSnapshot
    result_status: Literal["formal", "provisional", "review_required", "unscorable"]
    profile_eligibility: bool
    profile_ineligibility_reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    dimensions: list[EvaluationDimensionResultCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def formal_result_must_pass_its_supplied_gate(self):
        if self.result_status == "formal" and not self.quality_gate.eligible:
            raise ValueError("formal run requires an eligible quality gate")
        if self.profile_eligibility and self.result_status != "formal":
            raise ValueError("only formal runs may be profile eligible in V3 foundation")
        if self.profile_eligibility and self.profile_ineligibility_reasons:
            raise ValueError("eligible run cannot have profile ineligibility reasons")
        return self


class EvaluationDimensionResultRead(EvaluationDimensionResultCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    evaluation_run_id: UUID
    created_at: datetime


class EvaluationReviewRevisionCreate(BaseModel):
    dimension_result_id: UUID | None = None
    review_action: Literal["confirmed", "corrected", "unjudgeable"]
    automatic_value_snapshot: dict[str, Any] = Field(default_factory=dict)
    revised_value_snapshot: dict[str, Any] = Field(default_factory=dict)
    evidence_override: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    reason_code: Literal["asr_mismatch", "audio_unavailable", "noise", "task_not_applicable", "not_observed", "insufficient_evidence", "other"] | None = None
    reviewer_user_id: UUID | None = None
    recomputed_run_id: UUID | None = None
    review_request_key: str | None = Field(default=None, max_length=64)


class EvaluationReviewRevisionRead(EvaluationReviewRevisionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    evaluation_run_id: UUID
    created_at: datetime


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_profile_id: UUID
    domain: str
    source_type: str
    source_id: UUID
    algorithm_version: str
    input_fingerprint: str | None
    config_snapshot: dict[str, Any]
    input_provenance: InputProvenanceSnapshot
    quality_gate: QualityGateSnapshot
    result_status: str
    profile_eligibility: bool
    profile_ineligibility_reasons: list[str]
    limitations: list[str]
    adoption_status: str
    supersedes_run_id: UUID | None
    created_at: datetime
    dimension_results: list[EvaluationDimensionResultRead] = Field(default_factory=list)
    review_revisions: list[EvaluationReviewRevisionRead] = Field(default_factory=list)
