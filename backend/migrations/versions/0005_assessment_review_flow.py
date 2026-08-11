"""add assessment review flow

Revision ID: 0005_assessment_review_flow
Revises: 0004_add_therapist_role
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_assessment_review_flow"
down_revision = "0004_add_therapist_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_sessions",
        sa.Column("source_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assessment_sessions",
        sa.Column("review_status", sa.String(length=32), server_default="pending_review", nullable=False),
    )
    op.add_column(
        "assessment_sessions",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assessment_sessions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("assessment_sessions", sa.Column("therapist_notes", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_assessment_sessions_source_attempt_id_attempts",
        "assessment_sessions",
        "attempts",
        ["source_attempt_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_assessment_sessions_reviewed_by_user_id_users",
        "assessment_sessions",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_assessment_sessions_source_attempt_id"),
        "assessment_sessions",
        ["source_attempt_id"],
        unique=False,
    )
    op.alter_column("assessment_sessions", "review_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_assessment_sessions_source_attempt_id"), table_name="assessment_sessions")
    op.drop_constraint(
        "fk_assessment_sessions_reviewed_by_user_id_users",
        "assessment_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_assessment_sessions_source_attempt_id_attempts",
        "assessment_sessions",
        type_="foreignkey",
    )
    op.drop_column("assessment_sessions", "therapist_notes")
    op.drop_column("assessment_sessions", "reviewed_at")
    op.drop_column("assessment_sessions", "reviewed_by_user_id")
    op.drop_column("assessment_sessions", "review_status")
    op.drop_column("assessment_sessions", "source_attempt_id")
