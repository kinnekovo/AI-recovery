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


class TherapistPatientAssignmentCreate(BaseModel):
    therapist_user_id: UUID
    patient_user_id: UUID


class TherapistPatientAssignmentRead(BaseModel):
    assignment_id: UUID
    therapist_user_id: UUID
    patient_user_id: UUID
    patient_profile_id: UUID
    status: str
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


class TherapistStageAssessmentRead(BaseModel):
    assessment_id: UUID
    assessment_type: str
    review_status: str
    assessed_at: datetime
    reviewed_at: datetime | None = None
    therapist_notes: str | None = None
    metrics: dict


class TherapistStageReportRead(BaseModel):
    patient_user_id: UUID
    patient_profile_id: UUID
    username: str
    date_from: datetime | None = None
    date_to: datetime | None = None
    training_count: int
    analyzed_attempt_count: int
    failed_analysis_count: int
    low_quality_attempt_count: int
    low_quality_rate: float
    provider_failure_count: int
    process_summary: TherapistTrendBucketRead
    assessments: list[TherapistStageAssessmentRead]
    therapist_notes: list[str]


class TherapistTrialQualityRead(BaseModel):
    patient_count: int
    training_session_count: int
    completed_session_count: int
    completion_rate: float
    attempt_count: int
    missing_audio_count: int
    missing_audio_rate: float
    failed_analysis_count: int
    low_quality_attempt_count: int
    low_quality_rate: float
    provider_failure_count: int
