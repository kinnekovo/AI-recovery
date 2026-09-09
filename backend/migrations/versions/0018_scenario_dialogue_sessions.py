"""add multi-turn scenario dialogue sessions

Revision ID: 0018_scenario_dialogue_sessions
Revises: 0017_scenario_expression_reviews
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_scenario_dialogue_sessions"
down_revision = "0017_scenario_expression_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_dialogue_sessions",
        sa.Column("training_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_sessions.id"), nullable=False),
        sa.Column("session_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session_tasks.id"), nullable=False, unique=True),
        sa.Column("contract_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("status", sa.Enum("active", "completed", "aborted", name="dialogue_status"), nullable=False),
        sa.Column("current_state", sa.Enum("opening", "collecting", "clarifying", "repairing", "confirming", "completed", "turn_limit_reached", name="dialogue_state"), nullable=False),
        sa.Column("patient_turn_count", sa.Integer(), nullable=False),
        sa.Column("prompt_count", sa.Integer(), nullable=False),
        sa.Column("maximum_prompt_level", sa.Integer(), nullable=False),
        sa.Column("evaluation_role", sa.String(40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "scenario_dialogue_turns",
        sa.Column("dialogue_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_dialogue_sessions.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.Enum("agent", "patient", name="dialogue_speaker"), nullable=False),
        sa.Column("dialogue_act", sa.String(40), nullable=False),
        sa.Column("text", sa.String(2000), nullable=False),
        sa.Column("audio_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("asr_provider", sa.String(40), nullable=True),
        sa.Column("semantic_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dialogue_session_id", "turn_index", name="uq_dialogue_turn_index"),
    )
    op.create_index("ix_scenario_dialogue_sessions_training_session_id", "scenario_dialogue_sessions", ["training_session_id"])
    op.create_index("ix_scenario_dialogue_turns_dialogue_session_id", "scenario_dialogue_turns", ["dialogue_session_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_dialogue_turns_dialogue_session_id", table_name="scenario_dialogue_turns")
    op.drop_index("ix_scenario_dialogue_sessions_training_session_id", table_name="scenario_dialogue_sessions")
    op.drop_table("scenario_dialogue_turns")
    op.drop_table("scenario_dialogue_sessions")
    op.execute("DROP TYPE dialogue_speaker")
    op.execute("DROP TYPE dialogue_state")
    op.execute("DROP TYPE dialogue_status")
