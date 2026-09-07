"""compatibility marker for agent voice clone fields

Revision ID: 0011_agent_voice_clone
Revises: 0010_phase4_p0
Create Date: 2026-09-02
"""

revision = "0011_agent_voice_clone"
down_revision = "0010_phase4_p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The current schema already contains the agent voice clone fields.
    # This revision preserves compatibility with databases stamped by an
    # earlier local migration that is no longer present in the repository.
    pass


def downgrade() -> None:
    pass
