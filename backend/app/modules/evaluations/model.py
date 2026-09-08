import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text, UniqueConstraint
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

    attempt = relationship("Attempt", back_populates="evaluations")
    metric: Mapped[EvaluationMetric] = relationship(back_populates="attempt_evaluations")
