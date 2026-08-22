from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.training.model import TrainingType


class TherapistPatientRead(BaseModel):
    user_id: UUID
    patient_profile_id: UUID
    username: str
    assessment_status: str
    training_status: str
    pending_review_count: int = 0
    latest_assessment_at: datetime | None = None
    created_at: datetime


class TherapistTrainingRecordRead(BaseModel):
    attempt_id: UUID
    session_id: UUID
    created_at: datetime
    training_type: TrainingType
    task_title: str
    target_text: str
    analysis_status: str
    overall_score: int | None = None
    content_score: int | None = None
    clarity_score: int | None = None
    fluency_score: int | None = None
    loudness_score: int | None = None
    process_metrics: dict[str, float]
    process_details: dict | None = None
    audio_url: str | None = None
    asr_text: str | None = None
    feedback_summary: str
    recommendation_source: str | None = None
    recommendation_matched: bool = False


class TherapistTrendBucketRead(BaseModel):
    key: str
    label: str
    attempt_count: int
    avg_overall_score: float | None = None
    avg_script_accuracy: float | None = None
    avg_error_count: float | None = None
    avg_speech_rate: float | None = None
    avg_loudness: float | None = None
    summary: str


class TherapistTrainingTrendsRead(BaseModel):
    buckets: list[TherapistTrendBucketRead]
    overall_summary: str


class RecommendationNoteCreate(BaseModel):
    note: str | None = None


class RecommendationNoteRead(BaseModel):
    note: str | None = None
    updated_at: datetime | None = None
