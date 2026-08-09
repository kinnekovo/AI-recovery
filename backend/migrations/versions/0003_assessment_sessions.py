"""add assessment sessions

Revision ID: 0003_assessment_sessions
Revises: 0002_evaluation_models
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_assessment_sessions"
down_revision = "0002_evaluation_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    assessment_type = postgresql.ENUM(
        "baseline",
        "during",
        "after_30_days",
        "post_training",
        name="assessment_type",
        create_type=False,
    )
    assessment_type.create(op.get_bind(), checkfirst=True)
    evaluation_source = postgresql.ENUM("mock_ai", "human", "clinician", name="evaluation_source", create_type=False)

    op.create_table(
        "assessment_sessions",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_type", assessment_type, nullable=False),
        sa.Column("evaluation_source", evaluation_source, nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assessment_sessions_patient_profile_id"),
        "assessment_sessions",
        ["patient_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_assessment_sessions_patient_profile_id"), table_name="assessment_sessions")
    op.drop_table("assessment_sessions")
    sa.Enum(name="assessment_type").drop(op.get_bind(), checkfirst=True)
