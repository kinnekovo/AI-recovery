import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.modules.evaluations.model import EvaluationSource


class AssessmentType(str, enum.Enum):
    baseline = "baseline"
    during = "during"
    after_30_days = "after_30_days"
    post_training = "post_training"


class AssessmentSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assessment_sessions"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    assessment_type: Mapped[AssessmentType] = mapped_column(
        Enum(AssessmentType, name="assessment_type"), default=AssessmentType.baseline, nullable=False
    )
    evaluation_source: Mapped[EvaluationSource] = mapped_column(
        Enum(EvaluationSource, name="evaluation_source", create_type=False), default=EvaluationSource.human, nullable=False
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient_profile = relationship("PatientProfile")
