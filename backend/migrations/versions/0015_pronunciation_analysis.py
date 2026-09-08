"""add fine grained pronunciation analysis

Revision ID: 0015_pronunciation_analysis
Revises: 0014_attempt_analysis_errors
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_pronunciation_analysis"
down_revision = "0014_attempt_analysis_errors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pronunciation_analysis_results",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attempts.id"), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_version", sa.String(length=100), nullable=False),
        sa.Column("evaluation_mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("overall_accuracy", sa.Float(), nullable=True),
        sa.Column("fluency", sa.Float(), nullable=True),
        sa.Column("completion", sa.Float(), nullable=True),
        sa.Column("suggested_score", sa.Float(), nullable=True),
        sa.Column("intelligibility_proxy", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("coverage", sa.Float(), server_default="0", nullable=False),
        sa.Column("prosody_metrics", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("raw_provider_output", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), server_default="rehab-pronunciation-v1-shadow", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("review_status", sa.String(length=32), server_default="pending_review", nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pronunciation_analysis_results_attempt_id", "pronunciation_analysis_results", ["attempt_id"])
    op.create_table(
        "pronunciation_segments",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pronunciation_analysis_results.id"), nullable=False),
        sa.Column("level", sa.String(length=24), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("recognized_text", sa.Text(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("fluency", sa.Float(), nullable=True),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("reference_tone", sa.Integer(), nullable=True),
        sa.Column("recognized_tone", sa.Integer(), nullable=True),
        sa.Column("tone_correct", sa.Boolean(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pronunciation_segments_analysis_id", "pronunciation_segments", ["analysis_id"])
    op.create_table(
        "pronunciation_revisions",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pronunciation_analysis_results.id"), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pronunciation_segments.id"), nullable=True),
        sa.Column("metric_name", sa.String(length=80), nullable=False),
        sa.Column("original_value", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("revised_value", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("judgment", sa.String(length=32), nullable=False),
        sa.Column("error_category", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pronunciation_revisions_analysis_id", "pronunciation_revisions", ["analysis_id"])
    op.add_column("attempt_scores", sa.Column("pronunciation_shadow_score", sa.Integer(), nullable=True))
    op.add_column("attempt_scores", sa.Column("pronunciation_coverage", sa.Float(), nullable=True))
    op.add_column("attempt_scores", sa.Column("pronunciation_status", sa.String(length=32), nullable=True))
    op.add_column("attempt_scores", sa.Column("pronunciation_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("attempt_scores", "pronunciation_confidence")
    op.drop_column("attempt_scores", "pronunciation_status")
    op.drop_column("attempt_scores", "pronunciation_coverage")
    op.drop_column("attempt_scores", "pronunciation_shadow_score")
    op.drop_index("ix_pronunciation_revisions_analysis_id", table_name="pronunciation_revisions")
    op.drop_table("pronunciation_revisions")
    op.drop_index("ix_pronunciation_segments_analysis_id", table_name="pronunciation_segments")
    op.drop_table("pronunciation_segments")
    op.drop_index("ix_pronunciation_analysis_results_attempt_id", table_name="pronunciation_analysis_results")
    op.drop_table("pronunciation_analysis_results")
