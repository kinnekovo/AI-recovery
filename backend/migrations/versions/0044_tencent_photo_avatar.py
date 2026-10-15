"""Store per-agent Tencent photo avatar customization state.

Revision ID: 0044_tencent_photo_avatar
Revises: 0043_avatar_session_agent_null
"""

import sqlalchemy as sa
from alembic import op


revision = "0044_tencent_photo_avatar"
down_revision = "0043_avatar_session_agent_null"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("tencent_avatar_face_task_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_task_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_virtualman_key", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_resource_id", sa.String(length=160), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_material_url", sa.String(length=800), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("agents", sa.Column("tencent_avatar_stage", sa.String(length=32), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_error", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("tencent_avatar_photo_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("agents", "tencent_avatar_photo_version")
    op.drop_column("agents", "tencent_avatar_error")
    op.drop_column("agents", "tencent_avatar_stage")
    op.drop_column("agents", "tencent_avatar_status")
    op.drop_column("agents", "tencent_avatar_material_url")
    op.drop_column("agents", "tencent_avatar_resource_id")
    op.drop_column("agents", "tencent_avatar_virtualman_key")
    op.drop_column("agents", "tencent_avatar_task_id")
    op.drop_column("agents", "tencent_avatar_face_task_id")
