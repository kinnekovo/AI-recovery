from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.training.model import TrainingType


class TrainingSessionCreate(BaseModel):
    type: TrainingType


class TaskTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: TrainingType
    title: str
    instruction: str
    target_text: str
    content_level: str
    autonomy_level: str
    scene_prompt: str | None = None


class SessionTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_index: int
    prompt_level: int
    status: str
    task_template: TaskTemplateRead


class TrainingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    training_type: TrainingType
    status: str
    agent_id: UUID | None = None
    created_at: datetime
    session_tasks: list[SessionTaskRead]


class TodayTrainingRead(BaseModel):
    plan_id: UUID
    title: str
    status: str
    items_count: int


class TrainingRecommendationRead(BaseModel):
    id: UUID | None = None
    recommended_type: TrainingType
    headline: str
    reason: str
    focus_points: list[str]
    suggested_minutes: int
    content_level: str
    autonomy_level: str
    confidence: float
    profile_summary: str
    source: str = "system"
    review_status: str = "pending_review"
    therapist_notes: str | None = None
    updated_at: datetime | None = None
    task_template: TaskTemplateRead | None = None


class TrainingRecommendationReviewUpdate(BaseModel):
    recommended_type: TrainingType
    headline: str
    reason: str
    focus_points: list[str]
    suggested_minutes: int
    therapist_notes: str | None = None
