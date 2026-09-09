"""add scenario expression review queue

Revision ID: 0017_scenario_expression_reviews
Revises: 0016_intelligibility_reviews
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0017_scenario_expression_reviews"
down_revision = "0016_intelligibility_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_expression_reviews",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("review_status", sa.Enum("pending_review", "confirmed", "adjusted", name="scenario_review_status"), nullable=False),
        sa.Column("goal_status", sa.String(length=32), nullable=True),
        sa.Column("information_unit_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id"),
    )
    op.create_index("ix_scenario_expression_reviews_attempt_id", "scenario_expression_reviews", ["attempt_id"])
    # Preserve legacy materials for therapist editing, but never let an old
    # scenario silently use reference-sentence scoring after this release.
    op.execute(
        """
        UPDATE task_templates
        SET is_active = FALSE
        WHERE task_type = 'scenario'
          AND (
              COALESCE(scoring_config ->> 'mode', '') <> 'functional_scenario'
              OR BTRIM(COALESCE(scoring_config ->> 'version', '')) = ''
              OR BTRIM(COALESCE(scoring_config ->> 'display_prompt', '')) = ''
              OR BTRIM(COALESCE(scoring_config ->> 'communication_goal', '')) = ''
              OR COALESCE(jsonb_array_length(
                    CASE WHEN jsonb_typeof(scoring_config -> 'required_information_units') = 'array'
                         THEN scoring_config -> 'required_information_units'
                         ELSE '[]'::jsonb END
                 ), 0) < 2
              OR COALESCE(jsonb_array_length(
                    CASE WHEN jsonb_typeof(scoring_config -> 'goal_requirements') = 'array'
                         THEN scoring_config -> 'goal_requirements'
                         ELSE '[]'::jsonb END
                 ), 0) = 0
              OR COALESCE(jsonb_array_length(
                    CASE WHEN jsonb_typeof(scoring_config -> 'prompt_hints') = 'array'
                         THEN scoring_config -> 'prompt_hints'
                         ELSE '[]'::jsonb END
                 ), 0) = 0
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_scenario_expression_reviews_attempt_id", table_name="scenario_expression_reviews")
    op.drop_table("scenario_expression_reviews")
    op.execute("DROP TYPE scenario_review_status")
