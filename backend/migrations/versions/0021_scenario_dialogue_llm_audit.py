"""add llm audit fields to dialogue turns

Revision ID: 0021_scenario_dialogue_llm
Revises: 0020_scenario_dialogue_review
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_scenario_dialogue_llm"
down_revision = "0020_scenario_dialogue_review"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scenario_dialogue_turns", sa.Column("llm_provider", sa.String(40), nullable=True))
    op.add_column("scenario_dialogue_turns", sa.Column("llm_model_version", sa.String(120), nullable=True))
    op.add_column("scenario_dialogue_turns", sa.Column("llm_prompt_version", sa.String(80), nullable=True))

def downgrade() -> None:
    op.drop_column("scenario_dialogue_turns", "llm_prompt_version")
    op.drop_column("scenario_dialogue_turns", "llm_model_version")
    op.drop_column("scenario_dialogue_turns", "llm_provider")
