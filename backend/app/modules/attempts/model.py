import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Attempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attempts"

    session_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session_tasks.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    audio_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    prompt_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requested_help: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audio_quality: Mapped[str | None] = mapped_column(nullable=True)
    analysis_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    analysis_error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status"), default=AnalysisStatus.pending, nullable=False
    )

    session_task = relationship("SessionTask")
    audio_file = relationship("FileAsset")
    score = relationship("AttemptScore", back_populates="attempt", uselist=False)
    evaluations = relationship("AttemptEvaluation", back_populates="attempt", cascade="all, delete-orphan")
