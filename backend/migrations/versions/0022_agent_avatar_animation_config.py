"""store local 2.5D avatar layout anchors

Revision ID: 0022_agent_avatar_animation
Revises: 0021_scenario_dialogue_llm
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022_agent_avatar_animation"
down_revision = "0021_scenario_dialogue_llm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("avatar_animation_config", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "avatar_animation_config")
