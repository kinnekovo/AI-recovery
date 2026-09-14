import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AvatarVideoTaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class AvatarVideoTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "avatar_video_tasks"
    __table_args__ = (UniqueConstraint("owner_user_id", "cache_key", name="uq_avatar_video_tasks_owner_cache_key"),)

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    audio_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    video_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[AvatarVideoTaskStatus] = mapped_column(
        Enum(AvatarVideoTaskStatus, name="avatar_video_task_status"), default=AvatarVideoTaskStatus.queued, nullable=False, index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    owner = relationship("User", foreign_keys=[owner_user_id])
    agent = relationship("Agent", foreign_keys=[agent_id])
    audio_file = relationship("FileAsset", foreign_keys=[audio_file_id])
    video_file = relationship("FileAsset", foreign_keys=[video_file_id])


from app.modules.agents.model import Agent  # noqa: E402,F401
from app.modules.files.model import FileAsset  # noqa: E402,F401
from app.modules.users.model import User  # noqa: E402,F401
