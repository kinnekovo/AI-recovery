"""Allow shared Tencent avatar sessions without a personal agent.

Revision ID: 0043_avatar_session_agent_null
Revises: 0042_therapist_review_loop
"""

from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0043_avatar_session_agent_null"
down_revision = "0042_therapist_review_loop"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("avatar_sessions", "agent_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade():
    op.alter_column("avatar_sessions", "agent_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
