from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PronunciationSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    level: str
    ordinal: int
    reference_text: str | None = None
    recognized_text: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    accuracy: float | None = None
    fluency: float | None = None
    match_type: str
    reference_tone: int | None = None
    recognized_tone: int | None = None
    tone_correct: bool | None = None


class PronunciationRevisionCreate(BaseModel):
    segment_id: UUID | None = None
    metric_name: str = Field(min_length=1, max_length=80)
    revised_value: dict
    judgment: str = Field(pattern="^(confirmed|corrected|unjudgeable)$")
    error_category: str | None = Field(default=None, max_length=80)
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_reason_for_correction(self):
        if self.judgment == "corrected" and not self.error_category:
            raise ValueError("修正结果时必须填写错误类别")
        return self


class PronunciationRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_id: UUID
    segment_id: UUID | None = None
    metric_name: str
    original_value: dict
    revised_value: dict
    judgment: str
    error_category: str | None = None
    reason: str | None = None
    reviewed_by_user_id: UUID
    created_at: datetime


class IntelligibilityReviewCreate(BaseModel):
    listener_role: str = Field(min_length=1, max_length=80)
    listener_transcript: str = Field(min_length=1, max_length=2000)
    understood_percent: float = Field(ge=0, le=100)
    playback_count: int = Field(default=1, ge=1, le=20)
    listening_environment: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class IntelligibilityReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_id: UUID
    listener_role: str
    listener_transcript: str
    understood_percent: float
    playback_count: int
    listening_environment: str | None = None
    notes: str | None = None
    recorded_by_user_id: UUID
    created_at: datetime


class PronunciationAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_id: UUID
    provider: str
    provider_version: str
    evaluation_mode: str
    status: str
    overall_accuracy: float | None = None
    fluency: float | None = None
    completion: float | None = None
    suggested_score: float | None = None
    intelligibility_proxy: float | None = None
    confidence: float | None = None
    coverage: float
    prosody_metrics: dict
    algorithm_version: str
    error_code: str | None = None
    error_message: str | None = None
    review_status: str
    reviewed_by_user_id: UUID | None = None
    segments: list[PronunciationSegmentRead] = Field(default_factory=list)
    revisions: list[PronunciationRevisionRead] = Field(default_factory=list)
    intelligibility_reviews: list[IntelligibilityReviewRead] = Field(default_factory=list)
    created_at: datetime


class PatientPronunciationRead(BaseModel):
    attempt_id: UUID
    status: str
    overall_accuracy: float | None = None
    fluency: float | None = None
    completion: float | None = None
    intelligibility_proxy: float | None = None
    confidence: float | None = None
    coverage: float
    prosody_metrics: dict
    error_code: str | None = None
    error_message: str | None = None
    segments: list[PronunciationSegmentRead] = Field(default_factory=list)
    created_at: datetime
