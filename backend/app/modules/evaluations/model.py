import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationMetricCategory(str, enum.Enum):
    process = "process"
    long_term_effect = "long_term_effect"


class EvaluationSource(str, enum.Enum):
    mock_ai = "mock_ai"
    system_rule = "system_rule"
    provider_ai = "provider_ai"
    human = "human"
    clinician = "clinician"


class EvaluationMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_metrics"

    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    category: Mapped[EvaluationMetricCategory] = mapped_column(
        Enum(EvaluationMetricCategory, name="evaluation_metric_category"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    normal_range: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    attempt_evaluations: Mapped[list["AttemptEvaluation"]] = relationship(back_populates="metric")


class AttemptEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attempt_evaluations"
    __table_args__ = (
        UniqueConstraint("attempt_id", "metric_id", "evaluation_source", name="uq_attempt_metric_source"),
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempts.id"), index=True)
    metric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_metrics.id"), index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_source: Mapped[EvaluationSource] = mapped_column(
        Enum(EvaluationSource, name="evaluation_source"), default=EvaluationSource.mock_ai, nullable=False
    )
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quality_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    attempt = relationship("Attempt", back_populates="evaluations")
    metric: Mapped[EvaluationMetric] = relationship(back_populates="attempt_evaluations")


class ScenarioReviewStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    adjusted = "adjusted"


class ScenarioExpressionReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Human confirmation for an automatically extracted scenario communication result."""

    __tablename__ = "scenario_expression_reviews"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attempts.id"), unique=True, index=True, nullable=False
    )
    review_status: Mapped[ScenarioReviewStatus] = mapped_column(
        Enum(ScenarioReviewStatus, name="scenario_review_status"),
        default=ScenarioReviewStatus.pending_review,
        nullable=False,
    )
    goal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    information_unit_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt = relationship("Attempt")
    reviewed_by = relationship("User")
