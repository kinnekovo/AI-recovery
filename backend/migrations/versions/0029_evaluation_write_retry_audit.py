"""add canonical evaluation shadow-write retry audit

Revision ID: 0029_eval_write_retry
Revises: 0028_eval_run_fingerprint
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029_eval_write_retry"
down_revision = "0028_eval_run_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_review_revisions", sa.Column("review_request_key", sa.String(length=64), nullable=True))
    op.create_index("uq_evaluation_review_revisions_request", "evaluation_review_revisions", ["evaluation_run_id", "review_request_key"], unique=True, postgresql_where=sa.text("review_request_key IS NOT NULL"))
    op.create_table("evaluation_write_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(length=40), nullable=False), sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False), sa.Column("algorithm_version", sa.String(length=120), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False), sa.Column("failure_stage", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=False), sa.Column("retry_required", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False), sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", "domain", "algorithm_version", "input_fingerprint", name="uq_evaluation_write_failure_input"),
    )
    op.create_index("ix_evaluation_write_failures_retry", "evaluation_write_failures", ["retry_required", "last_failed_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_write_failures_retry", table_name="evaluation_write_failures")
    op.drop_table("evaluation_write_failures")
    op.drop_index("uq_evaluation_review_revisions_request", table_name="evaluation_review_revisions")
    op.drop_column("evaluation_review_revisions", "review_request_key")
