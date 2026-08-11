"""add ability profiles

Revision ID: 0006_ability_profiles
Revises: 0005_assessment_review_flow
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_ability_profiles"
down_revision = "0005_assessment_review_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ability_profiles",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_content_level", sa.String(length=8), nullable=False),
        sa.Column("current_autonomy_level", sa.String(length=8), nullable=False),
        sa.Column("avg_script_accuracy_recent", sa.Float(), nullable=True),
        sa.Column("avg_error_count_recent", sa.Float(), nullable=True),
        sa.Column("avg_speech_rate_recent", sa.Float(), nullable=True),
        sa.Column("avg_loudness_recent", sa.Float(), nullable=True),
        sa.Column("assessment_summary", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_profile_id"),
    )
    op.create_index(op.f("ix_ability_profiles_patient_profile_id"), "ability_profiles", ["patient_profile_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_ability_profiles_patient_profile_id"), table_name="ability_profiles")
    op.drop_table("ability_profiles")
