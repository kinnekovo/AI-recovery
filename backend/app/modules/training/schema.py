from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.avatar_videos.schema import AvatarVideoTaskBrief
from app.modules.training.model import TrainingType


class TrainingSessionCreate(BaseModel):
    type: TrainingType
    scenario_mode: str = "training"
    recommendation_id: UUID | None = None
    recommendation_source: str | None = None
    recommendation_headline: str | None = None
    recommendation_task_ids: list[UUID] | None = None


class AvatarSpeechCreate(BaseModel):
    scene: str
    session_id: UUID | None = None
    session_task_id: UUID | None = None
    text: str


class AvatarSpeechRead(BaseModel):
    text: str
    audio_file_id: UUID | None = None
    audio_url: str | None = None
    provider: str
    fallback: bool = False
    cached: bool = False
    video_task: AvatarVideoTaskBrief | None = None


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
    scoring_config: dict = {}
    tags: list[str] = []
    recommendation_weight: int = 50
    is_active: bool = True


class TaskTemplateCreate(BaseModel):
    task_type: TrainingType
    title: str
    instruction: str
    target_text: str
    content_level: str = "L1"
    autonomy_level: str = "S1"
    scene_prompt: str | None = None
    scoring_config: dict = {}
    tags: list[str] = []
    recommendation_weight: int = 50
    is_active: bool = True


class TaskTemplateUpdate(BaseModel):
    title: str | None = None
    instruction: str | None = None
    target_text: str | None = None
    content_level: str | None = None
    autonomy_level: str | None = None
    scene_prompt: str | None = None
    scoring_config: dict | None = None
    tags: list[str] | None = None
    recommendation_weight: int | None = None
    is_active: bool | None = None


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
    recommendation_review_id: UUID | None = None
    recommendation_source: str | None = None
    recommendation_snapshot: dict | None = None
    recommendation_matched: bool
    created_at: datetime
    session_tasks: list[SessionTaskRead]


class TodayTrainingRead(BaseModel):
    plan_id: UUID
    title: str
    status: str
    items_count: int
    recommended_completed: bool = False
    completed_recommended_sessions: int = 0


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
    task_sequence: list[TaskTemplateRead] = []
    policy_version: str = "phase4.3"
    adaptation_note: str | None = None
    reminder: str | None = None


class TrainingRecommendationReviewUpdate(BaseModel):
    recommended_type: TrainingType
    headline: str
    reason: str
    focus_points: list[str]
    suggested_minutes: int
    therapist_notes: str | None = None


class RecommendationEffectRead(BaseModel):
    session_id: UUID
    created_at: datetime
    training_type: TrainingType
    recommendation_source: str | None = None
    recommendation_headline: str | None = None
    recommendation_matched: bool
    status: str
    metrics: dict[str, float]
    summary: str


class RecommendationEffectSummaryRead(BaseModel):
    total_recommended_sessions: int
    completed_recommended_sessions: int
    matched_sessions: int
    trend_status: str
    trend_summary: str
    strategy_hint: str
    evidence_points: list[str]
    attribution_points: list[str] = []
    reminder_level: str = "info"
    patient_reminder: str | None = None
    family_reminder: str | None = None
    therapist_reminder: str | None = None
    latest: list[RecommendationEffectRead]


class StrategyFeedbackCreate(BaseModel):
    judgment: str
    reason: str | None = None
    next_strategy: str | None = None


class StrategyFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_profile_id: UUID
    therapist_user_id: UUID
    trend_status: str
    judgment: str
    reason: str | None = None
    next_strategy: str | None = None
    created_at: datetime


class FamilyObservationRead(BaseModel):
    patient_username: str
    training_count: int
    completed_recommended_sessions: int
    last_training_at: datetime | None = None
    adherence_summary: str = "还没有训练记录。"
    recommendation_headline: str
    recommendation_source: str
    trend_summary: str
    strategy_hint: str
    therapist_note: str | None = None
    reminder_level: str = "info"
    family_reminder: str | None = None
    current_level_label: str = "观察中"
    progress_label: str = "继续观察"
    progress_percent: int = 0
    level_items: list[dict] = []
    trend_items: list[dict] = []
    recent_records: list[dict] = []
    bound_patients: list[dict] = []
    selected_patient_user_id: UUID | None = None


class Phase3DemoStatusRead(BaseModel):
    has_patient: bool
    has_recommendation: bool
    has_therapist_review: bool
    has_recommended_training: bool
    has_effect_trend: bool
    has_strategy_feedback: bool
    next_step: str
