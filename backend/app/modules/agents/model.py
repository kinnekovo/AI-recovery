import enum
import uuid

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentGenerationStatus(str, enum.Enum):
    draft = "draft"
    voice_training = "voice_training"
    voice_ready = "voice_ready"
    ready = "ready"
    failed = "failed"


class AliyunAvatarStatus(str, enum.Enum):
    pending = "pending"
    provisioning = "provisioning"
    ready = "ready"
    failed = "failed"
    manual_review = "manual_review"


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agents"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    relationship: Mapped[str] = mapped_column(String(80), nullable=False)
    personality_style: Mapped[str] = mapped_column(String(120), default="gentle", nullable=False)
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    avatar_animation_config: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    avatar_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aliyun_avatar_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    aliyun_chat_config_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    aliyun_avatar_source_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    aliyun_avatar_status: Mapped[AliyunAvatarStatus] = mapped_column(
        Enum(AliyunAvatarStatus, name="aliyun_avatar_status"), default=AliyunAvatarStatus.pending, nullable=False
    )
    aliyun_avatar_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    voice_sample_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    welcome_audio_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    voice_external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    voice_clone_task_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    voice_training_text_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    voice_training_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
