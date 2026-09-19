import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.modules.evaluations.model import EvaluationSource


class AssessmentType(str, enum.Enum):
    baseline = "baseline"
    during = "during"
    after_30_days = "after_30_days"
    post_training = "post_training"


class AssessmentReviewStatus(str, enum.Enum):
    auto_generated = "auto_generated"
    pending_review = "pending_review"
    confirmed = "confirmed"
    adjusted = "adjusted"


class AssessmentSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assessment_sessions"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    source_attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=True)
    assessment_type: Mapped[AssessmentType] = mapped_column(
        Enum(AssessmentType, name="assessment_type"), default=AssessmentType.baseline, nullable=False
    )
    evaluation_source: Mapped[EvaluationSource] = mapped_column(
        Enum(EvaluationSource, name="evaluation_source", create_type=False), default=EvaluationSource.human, nullable=False
    )
    review_status: Mapped[AssessmentReviewStatus] = mapped_column(
        String(32), default=AssessmentReviewStatus.pending_review.value, nullable=False
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    therapist_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    instrument_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instrument_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    language_locale: Mapped[str | None] = mapped_column(String(40), nullable=True)
    localization_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    assessment_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    administered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    administrator_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    qualification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_item_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    subscale_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    total_result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    missing_items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    score_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    administration_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    device_and_environment: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol_deviations: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    protocol_deviation_reasons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    comparison_baseline_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id"), nullable=True)
    comparability_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    non_comparable_reasons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    patient_profile = relationship("PatientProfile")
    source_attempt = relationship("Attempt")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id])
