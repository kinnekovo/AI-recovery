import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AttemptAnalysisResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attempt_analysis_results"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempts.id"), unique=True)
    asr_text: Mapped[str] = mapped_column(Text, nullable=False)
    acoustic_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    semantic_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    raw_model_output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), default="mock-v1", nullable=False)


class AttemptScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attempt_scores"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempts.id"), unique=True)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    content_score: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fluency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    loudness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_dependence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(24), default="repeat", nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(80), default="rehab-score-v2", nullable=False)
    scoring_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_scorable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    main_strength: Mapped[str] = mapped_column(String(255), nullable=False)
    main_issue: Mapped[str] = mapped_column(String(255), nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)

    attempt = relationship("Attempt", back_populates="score")
