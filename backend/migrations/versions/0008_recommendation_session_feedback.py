"""add recommendation session feedback fields

Revision ID: 0008_rec_feedback
Revises: 0007_rec_reviews
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_rec_feedback"
down_revision = "0007_rec_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("training_sessions", sa.Column("recommendation_review_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("training_sessions", sa.Column("recommendation_source", sa.String(length=24), nullable=True))
    op.add_column("training_sessions", sa.Column("recommendation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "training_sessions",
        sa.Column("recommendation_matched", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_foreign_key(
        "fk_training_sessions_recommendation_review_id",
        "training_sessions",
        "training_recommendation_reviews",
        ["recommendation_review_id"],
        ["id"],
    )
    op.alter_column("training_sessions", "recommendation_matched", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_training_sessions_recommendation_review_id", "training_sessions", type_="foreignkey")
    op.drop_column("training_sessions", "recommendation_matched")
    op.drop_column("training_sessions", "recommendation_snapshot")
    op.drop_column("training_sessions", "recommendation_source")
    op.drop_column("training_sessions", "recommendation_review_id")
