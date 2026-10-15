"""Store Tencent Digital Human voice clone state.

Revision ID: 0045_tencent_voice_clone
Revises: 0044_tencent_photo_avatar
"""

import sqlalchemy as sa
from alembic import op


revision = "0045_tencent_voice_clone"
down_revision = "0044_tencent_photo_avatar"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("agents")}
    columns = [
        sa.Column("voice_clone_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("voice_clone_stage", sa.String(length=32), nullable=True),
        sa.Column("voice_clone_error", sa.String(length=500), nullable=True),
        sa.Column("voice_sample_url", sa.String(length=1000), nullable=True),
        sa.Column("voice_gender", sa.Integer(), nullable=True),
    ]
    for column in columns:
        if column.name not in existing:
            op.add_column("agents", column)


def downgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("agents")}
    for column_name in ("voice_gender", "voice_sample_url", "voice_clone_error", "voice_clone_stage", "voice_clone_status"):
        if column_name in existing:
            op.drop_column("agents", column_name)
