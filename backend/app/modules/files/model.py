import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FileType(str, enum.Enum):
    agent_image = "agent_image"
    voice_sample = "voice_sample"
    training_audio = "training_audio"
    generated_audio = "generated_audio"


class FileStatus(str, enum.Enum):
    active = "active"
    deleted = "deleted"


class FileAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "files"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType, name="file_type"), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(600), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[FileStatus] = mapped_column(Enum(FileStatus, name="file_status"), default=FileStatus.active, nullable=False)

    owner = relationship("User")
