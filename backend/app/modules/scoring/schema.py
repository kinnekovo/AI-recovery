from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScoreDimensions(BaseModel):
    content: int
    clarity: int
    fluency: int
    loudness: int
    prompt_dependence: int


class ScoreFeedback(BaseModel):
    strength: str
    improve: str


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_id: UUID
    overall_score: int
    dimensions: ScoreDimensions
    feedback: ScoreFeedback
    transcript: str | None = None


class ProcessMetricsRead(BaseModel):
    script_accuracy: float
    error_count: float
    speech_rate: float
    loudness: float


class TrainingFeedbackItem(BaseModel):
    metric: str
    current_performance: str
    suggestion: str


class TrainingFeedbackRead(BaseModel):
    attempt_id: UUID
    process_metrics: ProcessMetricsRead
    feedback: list[TrainingFeedbackItem]
    transcript: str | None = None
    audio_url: str | None = None
    process_details: dict | None = None
    pronunciation: dict | None = None
