"""V3.8 therapist-approved controlled Policy V2 action records.

Revision ID: 0038_controlled_activation
Revises: 0037_policy_validation_failures
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0038_controlled_activation"
down_revision = "0037_policy_validation_failures"
branch_labels = None
depends_on = None
U = postgresql.UUID(as_uuid=True)
J = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

def upgrade():
    op.create_table("controlled_action_proposals",
        sa.Column("id", U, primary_key=True), sa.Column("policy_decision_id", U, sa.ForeignKey("policy_decisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_profile_id", U, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_training_session_id", U, sa.ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False), sa.Column("proposed_value", J, nullable=False), sa.Column("current_value", J, nullable=False),
        sa.Column("expected_scope", J, nullable=False), sa.Column("reason_codes", J, nullable=False), sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("rules_version", sa.String(64), nullable=False), sa.Column("validation_run_id", U, sa.ForeignKey("policy_validation_runs.id", ondelete="RESTRICT")),
        sa.Column("profile_snapshot_id", U, sa.ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT")), sa.Column("activation_policy_version", sa.String(64), nullable=False),
        sa.Column("proposal_fingerprint", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending_review','approved','rejected','expired','cancelled','applied','failed','rolled_back')", name="ck_controlled_proposal_status"),
        sa.CheckConstraint("action_type IN ('training_focus_override','difficulty_step_adjustment')", name="ck_controlled_action_type"), sa.UniqueConstraint("proposal_fingerprint", name="uq_controlled_proposal_fingerprint"))
    op.create_index("ix_controlled_proposal_patient", "controlled_action_proposals", ["patient_profile_id", "status"])
    op.create_table("controlled_action_approvals", sa.Column("id", U, primary_key=True), sa.Column("proposal_id", U, sa.ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False), sa.Column("therapist_user_id", U, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("approved_action", J, nullable=False), sa.Column("approval_comment", sa.Text()), sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False), sa.Column("approval_valid_until", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("proposal_id", name="uq_controlled_approval_proposal"))
    op.create_table("controlled_action_executions", sa.Column("id", U, primary_key=True), sa.Column("proposal_id", U, sa.ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False), sa.Column("patient_profile_id", U, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False), sa.Column("training_session_id", U, sa.ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False), sa.Column("before_state", J, nullable=False), sa.Column("after_state", J, nullable=False), sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False), sa.Column("applied_by_user_id", U, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("failure_code", sa.String(80)), sa.Column("rolled_back_at", sa.DateTime(timezone=True)), sa.Column("rolled_back_by_user_id", U, sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("rollback_reason_code", sa.String(80)), sa.Column("rollback_comment", sa.Text()), sa.UniqueConstraint("proposal_id", name="uq_controlled_execution_proposal"))
    op.create_table("controlled_action_observations", sa.Column("id", U, primary_key=True), sa.Column("execution_id", U, sa.ForeignKey("controlled_action_executions.id", ondelete="RESTRICT"), nullable=False), sa.Column("outcome", sa.String(64), nullable=False), sa.Column("therapist_feedback", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("execution_id", name="uq_controlled_observation_execution"))
    op.create_table("controlled_action_audit_events", sa.Column("id", U, primary_key=True), sa.Column("proposal_id", U, sa.ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT"), nullable=False), sa.Column("execution_id", U, sa.ForeignKey("controlled_action_executions.id", ondelete="RESTRICT")), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("actor_user_id", U, sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("payload", J, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("controlled_action_safety_events", sa.Column("id", U, primary_key=True), sa.Column("proposal_id", U, sa.ForeignKey("controlled_action_proposals.id", ondelete="RESTRICT")), sa.Column("patient_profile_id", U, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("code", sa.String(80), nullable=False), sa.Column("details", J, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("controlled_action_safety_events"); op.drop_table("controlled_action_audit_events"); op.drop_table("controlled_action_observations"); op.drop_table("controlled_action_executions"); op.drop_table("controlled_action_approvals"); op.drop_index("ix_controlled_proposal_patient", table_name="controlled_action_proposals"); op.drop_table("controlled_action_proposals")
