"""persist the single Tencent VCL task and its required training text

Revision ID: 0023_agent_vcl_task
Revises: 0022_agent_avatar_animation
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_agent_vcl_task"
down_revision = "0022_agent_avatar_animation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_generation_status ADD VALUE IF NOT EXISTS 'voice_training'")
    op.add_column("agents", sa.Column("voice_clone_task_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("voice_training_text_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("voice_training_text", sa.String(length=500), nullable=True))
    op.create_unique_constraint("uq_agents_voice_clone_task_id", "agents", ["voice_clone_task_id"])


def downgrade() -> None:
    op.drop_constraint("uq_agents_voice_clone_task_id", "agents", type_="unique")
    op.drop_column("agents", "voice_training_text")
    op.drop_column("agents", "voice_training_text_id")
    op.drop_column("agents", "voice_clone_task_id")
    # PostgreSQL enum values are intentionally not removed: doing so is unsafe
    # when old rows may still contain the value.
