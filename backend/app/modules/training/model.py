import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TrainingType(str, enum.Enum):
    repeat = "repeat"
    scenario = "scenario"


class TrainingStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"


class RecommendationReviewStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    adjusted = "adjusted"


class TaskTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_templates"

    task_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType, name="training_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    target_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_level: Mapped[str] = mapped_column(String(8), default="L1", nullable=False)
    autonomy_level: Mapped[str] = mapped_column(String(8), default="S1", nullable=False)
    scene_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class TrainingPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_plans"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="今日训练", nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, name="training_status_enum"), default=TrainingStatus.planned, nullable=False
    )

    items: Mapped[list["TrainingPlanItem"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class TrainingPlanItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_plan_items"

    training_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plans.id"), index=True)
    task_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_templates.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, name="training_item_status"), default=TrainingStatus.planned, nullable=False
    )

    plan: Mapped[TrainingPlan] = relationship(back_populates="items")
    task_template: Mapped[TaskTemplate] = relationship()


class TrainingRecommendationReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_recommendation_reviews"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    recommended_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType, name="recommendation_training_type"), nullable=False)
    headline: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    focus_points: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    suggested_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    content_level: Mapped[str] = mapped_column(String(8), default="L1", nullable=False)
    autonomy_level: Mapped[str] = mapped_column(String(8), default="S1", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profile_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_status: Mapped[RecommendationReviewStatus] = mapped_column(
        Enum(RecommendationReviewStatus, name="recommendation_review_status"),
        default=RecommendationReviewStatus.pending_review,
        nullable=False,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    therapist_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient_profile = relationship("PatientProfile")
    reviewed_by = relationship("User")


class TrainingSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_sessions"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    training_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plans.id"), nullable=True)
    training_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType, name="session_training_type"), nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, name="session_status"), default=TrainingStatus.in_progress, nullable=False
    )

    session_tasks: Mapped[list["SessionTask"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "session_tasks"

    training_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True
    )
    training_plan_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_plan_items.id"), nullable=True
    )
    task_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_templates.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, name="session_task_status"), default=TrainingStatus.in_progress, nullable=False
    )

    session: Mapped[TrainingSession] = relationship(back_populates="session_tasks")
    task_template: Mapped[TaskTemplate] = relationship()
