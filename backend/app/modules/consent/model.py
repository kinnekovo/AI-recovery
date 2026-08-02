import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConsentStatus(str, enum.Enum):
    confirmed = "confirmed"
    revoked = "revoked"


class ConsentRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consents"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), default="mvp-v1", nullable=False)
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status"), default=ConsentStatus.confirmed, nullable=False
    )
