import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentGenerationStatus(str, enum.Enum):
    draft = "draft"
    voice_ready = "voice_ready"
    ready = "ready"
    failed = "failed"


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agents"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    relationship: Mapped[str] = mapped_column(String(80), nullable=False)
    personality_style: Mapped[str] = mapped_column(String(120), default="gentle", nullable=False)
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    voice_sample_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    welcome_audio_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    voice_external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    generation_status: Mapped[AgentGenerationStatus] = mapped_column(
        Enum(AgentGenerationStatus, name="agent_generation_status"),
        default=AgentGenerationStatus.draft,
        nullable=False,
    )
    image_consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    patient_profile = orm_relationship("PatientProfile", back_populates="agents", foreign_keys=[patient_profile_id])
    avatar_file = orm_relationship("FileAsset", foreign_keys=[avatar_file_id])
    voice_sample_file = orm_relationship("FileAsset", foreign_keys=[voice_sample_file_id])
    welcome_audio_file = orm_relationship("FileAsset", foreign_keys=[welcome_audio_file_id])


from app.modules.files.model import FileAsset  # noqa: E402,F401
