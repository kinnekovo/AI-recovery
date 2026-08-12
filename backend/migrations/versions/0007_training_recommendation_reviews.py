"""add training recommendation reviews

Revision ID: 0007_rec_reviews
Revises: 0006_ability_profiles
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_rec_reviews"
down_revision = "0006_ability_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    recommendation_training_type = postgresql.ENUM(
        "repeat",
        "scenario",
        name="recommendation_training_type",
        create_type=False,
    )
    recommendation_review_status = postgresql.ENUM(
        "pending_review",
        "confirmed",
        "adjusted",
        name="recommendation_review_status",
        create_type=False,
    )
    recommendation_training_type.create(op.get_bind(), checkfirst=True)
    recommendation_review_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "training_recommendation_reviews",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommended_type", recommendation_training_type, nullable=False),
        sa.Column("headline", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("focus_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_minutes", sa.Integer(), nullable=False),
        sa.Column("content_level", sa.String(length=8), nullable=False),
        sa.Column("autonomy_level", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("profile_summary", sa.Text(), nullable=False),
        sa.Column("review_status", recommendation_review_status, nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("therapist_notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_training_recommendation_reviews_patient_profile_id"),
        "training_recommendation_reviews",
        ["patient_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_training_recommendation_reviews_patient_profile_id"),
        table_name="training_recommendation_reviews",
    )
    op.drop_table("training_recommendation_reviews")
    postgresql.ENUM(name="recommendation_review_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="recommendation_training_type").drop(op.get_bind(), checkfirst=True)
