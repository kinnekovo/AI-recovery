"""add dialogue evaluation review audit

Revision ID: 0020_scenario_dialogue_review
Revises: 0019_scenario_dialogue_eval
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_scenario_dialogue_review"
down_revision = "0019_scenario_dialogue_eval"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scenario_dialogue_evaluations", sa.Column("evidence_overrides", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("scenario_dialogue_evaluations", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("scenario_dialogue_evaluations", sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("scenario_dialogue_evaluations", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column("scenario_dialogue_evaluations", "reviewed_at")
    op.drop_column("scenario_dialogue_evaluations", "reviewed_by_user_id")
    op.drop_column("scenario_dialogue_evaluations", "review_notes")
    op.drop_column("scenario_dialogue_evaluations", "evidence_overrides")
