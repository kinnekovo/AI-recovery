"""add deterministic multi-turn dialogue evaluations

Revision ID: 0019_scenario_dialogue_eval
Revises: 0018_scenario_dialogue_sessions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_scenario_dialogue_eval"
down_revision = "0018_scenario_dialogue_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_dialogue_evaluations",
        sa.Column("dialogue_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_dialogue_sessions.id"), nullable=False, unique=True),
        sa.Column("goal_status", sa.String(32), nullable=False),
        sa.Column("goal_score", sa.Float(), nullable=False),
        sa.Column("information_score", sa.Float(), nullable=False),
        sa.Column("response_score", sa.Float(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("independence_score", sa.Float(), nullable=False),
        sa.Column("repair_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenario_dialogue_evaluations_dialogue_session_id", "scenario_dialogue_evaluations", ["dialogue_session_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_dialogue_evaluations_dialogue_session_id", table_name="scenario_dialogue_evaluations")
    op.drop_table("scenario_dialogue_evaluations")
