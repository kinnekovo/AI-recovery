"""add immutable Profile V2 snapshots

Revision ID: 0033_profile_v2_snapshots
Revises: 0032_calibration_adjudication
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0033_profile_v2_snapshots"
down_revision = "0032_calibration_adjudication"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

def upgrade():
    op.create_table("patient_profile_snapshots",
        sa.Column("id", UUID, primary_key=True), sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("profile_schema_version", sa.String(64), nullable=False), sa.Column("mapping_version", sa.String(64), nullable=False), sa.Column("evidence_policy_version", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("as_of", sa.DateTime(timezone=True)), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("previous_snapshot_id", UUID, sa.ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT")), sa.Column("evidence_fingerprint", sa.String(64), nullable=False), sa.Column("payload", JSON, nullable=False),
        sa.UniqueConstraint("patient_profile_id", "evidence_fingerprint", name="uq_profile_snapshot_fingerprint"))
    op.create_index("ix_profile_snapshot_latest", "patient_profile_snapshots", ["patient_profile_id", "generated_at"])
    op.create_table("profile_evidence_links",
        sa.Column("id", UUID, primary_key=True), sa.Column("snapshot_id", UUID, sa.ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"), nullable=False), sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evaluation_run_id", UUID, sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False), sa.Column("assessment_session_id", UUID, sa.ForeignKey("assessment_sessions.id", ondelete="RESTRICT")),
        sa.Column("source_type", sa.String(40), nullable=False), sa.Column("source_id", UUID, nullable=False), sa.Column("profile_dimension_code", sa.String(120), nullable=False), sa.Column("source_dimension_code", sa.String(120), nullable=False), sa.Column("source_kind", sa.String(24), nullable=False), sa.Column("unit", sa.String(40)), sa.Column("metric_status", sa.String(20)), sa.Column("provider_version", sa.String(120)), sa.Column("canonical_result_status", sa.String(32), nullable=False), sa.Column("review_state", sa.String(32)), sa.Column("evidence_timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("metadata_snapshot", JSON, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("snapshot_id", "evaluation_run_id", "source_dimension_code", name="uq_profile_evidence_link"))
    op.create_index("ix_profile_evidence_snapshot", "profile_evidence_links", ["snapshot_id", "profile_dimension_code"])
    op.create_table("profile_build_failures",
        sa.Column("id", UUID, primary_key=True), sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False), sa.Column("input_fingerprint", sa.String(64), nullable=False), sa.Column("failure_stage", sa.String(80), nullable=False), sa.Column("error_code", sa.String(80), nullable=False), sa.Column("retry_required", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="1"), sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_retry_at", sa.DateTime(timezone=True)), sa.Column("resolved_snapshot_id", UUID, sa.ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("patient_profile_id", "input_fingerprint", name="uq_profile_build_failure_input"))

def downgrade():
    op.drop_table("profile_build_failures")
    op.drop_index("ix_profile_evidence_snapshot", table_name="profile_evidence_links"); op.drop_table("profile_evidence_links")
    op.drop_index("ix_profile_snapshot_latest", table_name="patient_profile_snapshots"); op.drop_table("patient_profile_snapshots")
