import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

JSONDocument = JSON().with_variant(JSONB, "postgresql")

class PolicyDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "policy_decisions"
    __table_args__ = (CheckConstraint("mode = 'shadow'", name="ck_policy_decisions_shadow_only"), UniqueConstraint("patient_profile_id", "input_fingerprint", name="uq_policy_decision_input"), Index("ix_policy_decision_latest", "patient_profile_id", "generated_at"))
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    profile_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"))
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_version: Mapped[str | None] = mapped_column(String(64))
    profile_mapping_version: Mapped[str | None] = mapped_column(String(64))
    profile_evidence_policy_version: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="shadow")
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)

class PolicyDecisionFeedback(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "policy_decision_feedback"
    __table_args__ = (UniqueConstraint("decision_id", "therapist_user_id", "review_round", name="uq_policy_feedback_round"),)
    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_decisions.id", ondelete="RESTRICT"), nullable=False)
    therapist_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    review_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    agreement: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class PolicyDecisionObservation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "policy_decision_observations"
    __table_args__ = (UniqueConstraint("decision_id", "training_session_id", name="uq_policy_observation_session"),)
    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_decisions.id", ondelete="RESTRICT"), nullable=False)
    training_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False)
    focus_match: Mapped[str] = mapped_column(String(24), nullable=False)
    difficulty_match: Mapped[str] = mapped_column(String(24), nullable=False)
    reassessment_match: Mapped[str] = mapped_column(String(24), nullable=False)
    actual_training_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class PolicyShadowFailure(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "policy_shadow_failures"
    __table_args__ = (UniqueConstraint("patient_profile_id", "input_fingerprint", name="uq_policy_failure_input"),)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    profile_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"))
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[str] = mapped_column(String(80), nullable=False)
    retry_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_failed_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_retry_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    resolved_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_decisions.id", ondelete="RESTRICT"))
