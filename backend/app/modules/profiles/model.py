import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AbilityProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ability_profiles"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patient_profiles.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    current_content_level: Mapped[str] = mapped_column(String(8), default="L1", nullable=False)
    current_autonomy_level: Mapped[str] = mapped_column(String(8), default="S1", nullable=False)
    avg_script_accuracy_recent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_error_count_recent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speech_rate_recent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_loudness_recent: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    patient_profile = relationship("PatientProfile")
