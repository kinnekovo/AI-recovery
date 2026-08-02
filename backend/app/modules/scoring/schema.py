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
