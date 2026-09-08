"""add formal rehabilitation evaluation sources

Revision ID: 0013_rehab_eval_sources
Revises: 0012_therapist_assign
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013_rehab_eval_sources"
down_revision = "0012_therapist_assign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE evaluation_source ADD VALUE IF NOT EXISTS 'system_rule'")
        op.execute("ALTER TYPE evaluation_source ADD VALUE IF NOT EXISTS 'provider_ai'")
    op.add_column("attempt_scores", sa.Column("task_type", sa.String(length=24), server_default="repeat", nullable=False))
    op.add_column(
        "attempt_scores",
        sa.Column("scoring_version", sa.String(length=80), server_default="legacy-score-v1", nullable=False),
    )
    op.add_column(
        "attempt_scores",
        sa.Column("scoring_config", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
    )
    op.add_column("attempt_scores", sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False))
    op.add_column("attempt_scores", sa.Column("is_scorable", sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    op.drop_column("attempt_scores", "is_scorable")
    op.drop_column("attempt_scores", "confidence")
    op.drop_column("attempt_scores", "scoring_config")
    op.drop_column("attempt_scores", "scoring_version")
    op.drop_column("attempt_scores", "task_type")
    # PostgreSQL enum values cannot be removed safely while rows may reference them.
