import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PronunciationAnalysisResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pronunciation_analysis_results"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attempts.id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    overall_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    fluency: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intelligibility_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prosody_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    raw_provider_output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), default="rehab-pronunciation-v1-shadow", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    attempt = relationship("Attempt")
    segments = relationship("PronunciationSegment", back_populates="analysis", cascade="all, delete-orphan")
    revisions = relationship("PronunciationRevision", back_populates="analysis", cascade="all, delete-orphan")
    intelligibility_reviews = relationship("IntelligibilityReview", back_populates="analysis", cascade="all, delete-orphan")


class PronunciationSegment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pronunciation_segments"

    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pronunciation_analysis_results.id"), index=True)
    level: Mapped[str] = mapped_column(String(24), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recognized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    fluency: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_tone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recognized_tone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tone_correct: Mapped[bool | None] = mapped_column(nullable=True)
    provider_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    analysis = relationship("PronunciationAnalysisResult", back_populates="segments")
    revisions = relationship("PronunciationRevision", back_populates="segment")


class PronunciationRevision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pronunciation_revisions"

    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pronunciation_analysis_results.id"), index=True)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pronunciation_segments.id"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    original_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    revised_value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    judgment: Mapped[str] = mapped_column(String(32), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    analysis = relationship("PronunciationAnalysisResult", back_populates="revisions")
    segment = relationship("PronunciationSegment", back_populates="revisions")


class IntelligibilityReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intelligibility_reviews"

    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pronunciation_analysis_results.id"), index=True)
    listener_role: Mapped[str] = mapped_column(String(80), nullable=False)
    listener_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    understood_percent: Mapped[float] = mapped_column(Float, nullable=False)
    playback_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    listening_environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    analysis = relationship("PronunciationAnalysisResult", back_populates="intelligibility_reviews")
