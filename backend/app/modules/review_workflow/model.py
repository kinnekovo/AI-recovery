import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, utc_now


JSONDocument = JSON().with_variant(JSONB, "postgresql")


class AttentionItemEvent(Base):
    __tablename__ = "attention_item_events"
    __table_args__ = (
        Index("ix_attention_item_events_item_created", "attention_item_id", "created_at"),
        Index("ix_attention_item_events_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attention_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attention_items.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_refs: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
