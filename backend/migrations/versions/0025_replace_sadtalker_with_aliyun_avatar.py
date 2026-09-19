"""replace SadTalker tasks with Alibaba Cloud avatar metadata

Revision ID: 0025_replace_sadtalker_with_aliyun_avatar
Revises: 0024_avatar_video_tasks
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0025_replace_sadtalker_with_aliyun_avatar"
down_revision = "0024_avatar_video_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old MP4s are deleted from storage by the deployment cleanup; remove their DB rows first.
    op.execute("DELETE FROM files WHERE file_type::text = 'generated_avatar_video'")
    op.drop_table("avatar_video_tasks")
    op.execute("DROP TYPE IF EXISTS avatar_video_task_status")
    op.execute("CREATE TYPE file_type_new AS ENUM ('agent_image', 'voice_sample', 'training_audio', 'generated_audio')")
    op.execute("ALTER TABLE files ALTER COLUMN file_type TYPE file_type_new USING file_type::text::file_type_new")
    op.execute("DROP TYPE file_type")
    op.execute("ALTER TYPE file_type_new RENAME TO file_type")

    avatar_status = postgresql.ENUM("pending", "provisioning", "ready", "failed", "manual_review", name="aliyun_avatar_status")
    avatar_status.create(op.get_bind(), checkfirst=True)
    op.add_column("agents", sa.Column("avatar_gender", sa.String(length=10), nullable=True))
    op.add_column("agents", sa.Column("aliyun_avatar_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("aliyun_chat_config_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("aliyun_avatar_source_file_id", sa.UUID(), nullable=True))
    op.add_column("agents", sa.Column("aliyun_avatar_status", avatar_status, nullable=False, server_default="pending"))
    op.add_column("agents", sa.Column("aliyun_avatar_error", sa.String(length=300), nullable=True))
    op.alter_column("agents", "aliyun_avatar_status", server_default=None)

    session_status = postgresql.ENUM("opening", "active", "closed", "failed", name="avatar_session_status")
    session_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "avatar_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("instance_id", sa.String(length=160), nullable=False),
        sa.Column("provider_session_id", sa.String(length=160), nullable=True),
        sa.Column("status", session_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_avatar_sessions_owner_user_id", "avatar_sessions", ["owner_user_id"])
    op.create_index("ix_avatar_sessions_agent_id", "avatar_sessions", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_avatar_sessions_agent_id", table_name="avatar_sessions")
    op.drop_index("ix_avatar_sessions_owner_user_id", table_name="avatar_sessions")
    op.drop_table("avatar_sessions")
    op.execute("DROP TYPE IF EXISTS avatar_session_status")
    op.drop_column("agents", "aliyun_avatar_error")
    op.drop_column("agents", "aliyun_avatar_status")
    op.drop_column("agents", "aliyun_avatar_source_file_id")
    op.drop_column("agents", "aliyun_chat_config_id")
    op.drop_column("agents", "aliyun_avatar_id")
    op.drop_column("agents", "avatar_gender")
    op.execute("DROP TYPE IF EXISTS aliyun_avatar_status")
    # Historical SadTalker task data was intentionally destroyed in upgrade.
    op.execute("CREATE TYPE file_type_old AS ENUM ('agent_image', 'voice_sample', 'training_audio', 'generated_audio', 'generated_avatar_video')")
    op.execute("ALTER TABLE files ALTER COLUMN file_type TYPE file_type_old USING file_type::text::file_type_old")
    op.execute("DROP TYPE file_type")
    op.execute("ALTER TYPE file_type_old RENAME TO file_type")
