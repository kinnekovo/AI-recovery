import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DialogueStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    aborted = "aborted"


class DialogueState(str, enum.Enum):
    opening = "opening"
    collecting = "collecting"
    clarifying = "clarifying"
    repairing = "repairing"
    confirming = "confirming"
    completed = "completed"
    turn_limit_reached = "turn_limit_reached"


class DialogueSpeaker(str, enum.Enum):
    agent = "agent"
    patient = "patient"


class ScenarioDialogueSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_dialogue_sessions"

    training_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True)
    session_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session_tasks.id"), unique=True)
    contract_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DialogueStatus] = mapped_column(Enum(DialogueStatus, name="dialogue_status"), default=DialogueStatus.active)
    current_state: Mapped[DialogueState] = mapped_column(Enum(DialogueState, name="dialogue_state"), default=DialogueState.opening)
    patient_turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maximum_prompt_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluation_role: Mapped[str] = mapped_column(String(40), default="training", nullable=False)


class ScenarioDialogueTurn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_dialogue_turns"
    __table_args__ = (UniqueConstraint("dialogue_session_id", "turn_index", name="uq_dialogue_turn_index"),)

    dialogue_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenario_dialogue_sessions.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[DialogueSpeaker] = mapped_column(Enum(DialogueSpeaker, name="dialogue_speaker"), nullable=False)
    dialogue_act: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    audio_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    asr_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    llm_model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    semantic_evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ScenarioDialogueEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_dialogue_evaluations"

    dialogue_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenario_dialogue_sessions.id"), unique=True, index=True
    )
    goal_status: Mapped[str] = mapped_column(String(32), nullable=False)
    goal_score: Mapped[float] = mapped_column(Float, nullable=False)
    information_score: Mapped[float] = mapped_column(Float, nullable=False)
    response_score: Mapped[float] = mapped_column(Float, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    independence_score: Mapped[float] = mapped_column(Float, nullable=False)
    repair_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(64), nullable=False)
