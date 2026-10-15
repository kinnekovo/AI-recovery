import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AvatarSessionStatus(str, enum.Enum):
    opening = "opening"
    active = "active"
    closed = "closed"
    failed = "failed"


class AvatarSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "avatar_sessions"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True, index=True)
    instance_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_session_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[AvatarSessionStatus] = mapped_column(
        Enum(AvatarSessionStatus, name="avatar_session_status"), default=AvatarSessionStatus.opening, nullable=False
    )
