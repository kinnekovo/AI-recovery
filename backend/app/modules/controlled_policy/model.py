import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

J = JSON().with_variant(JSONB, "postgresql")
PROPOSAL_STATUSES = "'pending_review','approved','rejected','expired','cancelled','applied','failed','rolled_back'"

class ControlledActionProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "controlled_action_proposals"
    __table_args__ = (
        CheckConstraint(f"status IN ({PROPOSAL_STATUSES})", name="ck_controlled_proposal_status"),
        CheckConstraint("action_type IN ('training_focus_override','difficulty_step_adjustment')", name="ck_controlled_action_type"),
        UniqueConstraint("proposal_fingerprint", name="uq_controlled_proposal_fingerprint"),
        Index("ix_controlled_proposal_patient", "patient_profile_id", "status"),
    )
    policy_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_decisions.id", ondelete="RESTRICT"), nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    target_training_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_value: Mapped[dict] = mapped_column(J, nullable=False)
    current_value: Mapped[dict] = mapped_column(J, nullable=False)
    expected_scope: Mapped[dict] = mapped_column(J, nullable=False)
    reason_codes: Mapped[list] = mapped_column(J, default=list, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_validation_runs.id", ondelete="RESTRICT"))
    profile_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"))
    activation_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

class ControlledActionApproval(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "controlled_action_approvals"
    __table_args__ = (UniqueConstraint("proposal_id", name="uq_controlled_approval_proposal"),)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False)
    therapist_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_action: Mapped[dict] = mapped_column(J, nullable=False)
    approval_comment: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    approval_valid_until: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

class ControlledActionExecution(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "controlled_action_executions"
    __table_args__ = (UniqueConstraint("proposal_id", name="uq_controlled_execution_proposal"),)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    training_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False)
    before_state: Mapped[dict] = mapped_column(J, nullable=False)
    after_state: Mapped[dict] = mapped_column(J, nullable=False)
    applied_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    applied_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    rolled_back_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    rolled_back_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    rollback_reason_code: Mapped[str | None] = mapped_column(String(80))
    rollback_comment: Mapped[str | None] = mapped_column(Text)

class ControlledActionObservation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "controlled_action_observations"
    __table_args__ = (UniqueConstraint("execution_id", name="uq_controlled_observation_execution"),)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_executions.id", ondelete="RESTRICT"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    therapist_feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class ControlledActionAuditEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "controlled_action_audit_events"
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_executions.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    payload: Mapped[dict] = mapped_column(J, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

class ControlledActionSafetyEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "controlled_action_safety_events"
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"))
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict] = mapped_column(J, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
