"""add therapist role

Revision ID: 0004_add_therapist_role
Revises: 0003_assessment_sessions
Create Date: 2026-08-10
"""
from alembic import op

revision = "0004_add_therapist_role"
down_revision = "0003_assessment_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'therapist'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be dropped safely without rebuilding the enum.
    pass
