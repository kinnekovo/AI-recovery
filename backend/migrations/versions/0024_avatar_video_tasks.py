"""add durable asynchronous avatar video tasks

Revision ID: 0024_avatar_video_tasks
Revises: 0023_agent_vcl_task
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0024_avatar_video_tasks"
down_revision = "0023_agent_vcl_task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE file_type ADD VALUE IF NOT EXISTS 'generated_avatar_video'")
    task_status = postgresql.ENUM(
        "queued", "running", "succeeded", "failed", name="avatar_video_task_status", create_type=False
    )
    task_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "avatar_video_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("audio_file_id", sa.UUID(), nullable=False),
        sa.Column("video_file_id", sa.UUID(), nullable=True),
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["audio_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["video_file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "cache_key", name="uq_avatar_video_tasks_owner_cache_key"),
    )
    op.create_index("ix_avatar_video_tasks_owner_user_id", "avatar_video_tasks", ["owner_user_id"])
    op.create_index("ix_avatar_video_tasks_agent_id", "avatar_video_tasks", ["agent_id"])
    op.create_index("ix_avatar_video_tasks_status", "avatar_video_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_avatar_video_tasks_status", table_name="avatar_video_tasks")
    op.drop_index("ix_avatar_video_tasks_agent_id", table_name="avatar_video_tasks")
    op.drop_index("ix_avatar_video_tasks_owner_user_id", table_name="avatar_video_tasks")
    op.drop_table("avatar_video_tasks")
    # PostgreSQL enum values are retained to avoid unsafe deletion when historical rows exist.
