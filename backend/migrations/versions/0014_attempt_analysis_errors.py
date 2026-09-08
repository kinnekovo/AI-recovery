"""store attempt analysis failure details

Revision ID: 0014_attempt_analysis_errors
Revises: 0013_rehab_eval_sources
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_attempt_analysis_errors"
down_revision = "0013_rehab_eval_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempts", sa.Column("analysis_error_code", sa.String(length=80), nullable=True))
    op.add_column("attempts", sa.Column("analysis_error_message", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("attempts", "analysis_error_message")
    op.drop_column("attempts", "analysis_error_code")
