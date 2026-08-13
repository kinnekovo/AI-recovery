"""add phase3 closure strategy feedback

Revision ID: 0009_phase3_close
Revises: 0008_rec_feedback
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_phase3_close"
down_revision = "0008_rec_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    judgment_enum = postgresql.ENUM("agree", "disagree", "observe", name="strategy_feedback_judgment", create_type=False)
    judgment_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "recommendation_strategy_feedbacks",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("therapist_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trend_status", sa.String(length=40), nullable=False),
        sa.Column("judgment", judgment_enum, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("next_strategy", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recommendation_strategy_feedbacks_patient_profile_id"),
        "recommendation_strategy_feedbacks",
        ["patient_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_strategy_feedbacks_therapist_user_id"),
        "recommendation_strategy_feedbacks",
        ["therapist_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recommendation_strategy_feedbacks_therapist_user_id"), table_name="recommendation_strategy_feedbacks")
    op.drop_index(op.f("ix_recommendation_strategy_feedbacks_patient_profile_id"), table_name="recommendation_strategy_feedbacks")
    op.drop_table("recommendation_strategy_feedbacks")
    postgresql.ENUM(name="strategy_feedback_judgment").drop(op.get_bind(), checkfirst=True)
