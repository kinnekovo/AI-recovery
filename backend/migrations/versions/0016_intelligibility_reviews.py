"""add manual intelligibility reviews

Revision ID: 0016_intelligibility_reviews
Revises: 0015_pronunciation_analysis
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_intelligibility_reviews"
down_revision = "0015_pronunciation_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligibility_reviews",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pronunciation_analysis_results.id"), nullable=False),
        sa.Column("listener_role", sa.String(length=80), nullable=False),
        sa.Column("listener_transcript", sa.Text(), nullable=False),
        sa.Column("understood_percent", sa.Float(), nullable=False),
        sa.Column("playback_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("listening_environment", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_intelligibility_reviews_analysis_id", "intelligibility_reviews", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_intelligibility_reviews_analysis_id", table_name="intelligibility_reviews")
    op.drop_table("intelligibility_reviews")
