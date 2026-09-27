"""Daily practice plans and stable extra-practice candidate pools."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0041_daily_practice_extra_pool"
down_revision = "0040_product_reset_v1"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    op.create_table(
        "daily_practice_plans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("training_plan_version_id", UUID, sa.ForeignKey("training_plan_versions.id"), nullable=True),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("generation_snapshot", JSON, nullable=False),
        sa.Column("published_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("patient_profile_id", "local_date", "version_number", name="uq_daily_practice_plan_version"),
    )
    op.create_index("ix_daily_practice_plans_patient_profile_id", "daily_practice_plans", ["patient_profile_id"])
    op.create_index("ix_daily_practice_plans_patient_date", "daily_practice_plans", ["patient_profile_id", "local_date"])
    op.create_table(
        "daily_practice_plan_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("daily_plan_id", UUID, sa.ForeignKey("daily_practice_plans.id"), nullable=False),
        sa.Column("task_template_id", UUID, sa.ForeignKey("task_templates.id"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("exercise_type", sa.String(32), nullable=False),
        sa.Column("sequence_role", sa.String(24), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("selection_source", sa.String(32), nullable=False),
        sa.Column("reason_codes", JSON, nullable=False),
        sa.Column("therapist_locked", sa.Boolean(), nullable=False),
        sa.Column("difficulty_snapshot", sa.String(32), nullable=True),
        sa.Column("content_snapshot", JSON, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("daily_plan_id", "order_index", name="uq_daily_plan_item_order"),
    )
    op.create_index("ix_daily_practice_plan_items_daily_plan_id", "daily_practice_plan_items", ["daily_plan_id"])
    op.create_table(
        "extra_practice_pools",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("generation_snapshot", JSON, nullable=False),
        sa.Column("refreshed_by_user", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("patient_profile_id", "local_date", "version_number", name="uq_extra_pool_version"),
    )
    op.create_index("ix_extra_practice_pools_patient_profile_id", "extra_practice_pools", ["patient_profile_id"])
    op.create_table(
        "extra_practice_pool_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("pool_id", UUID, sa.ForeignKey("extra_practice_pools.id"), nullable=False),
        sa.Column("task_template_id", UUID, sa.ForeignKey("task_templates.id"), nullable=False),
        sa.Column("exercise_type", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("selection_source", sa.String(32), nullable=False),
        sa.Column("display_reason", sa.String(120), nullable=False),
        sa.Column("difficulty_snapshot", sa.String(32), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("pool_id", "task_template_id", name="uq_extra_pool_task"),
    )
    op.create_index("ix_extra_practice_pool_items_pool_id", "extra_practice_pool_items", ["pool_id"])


def downgrade():
    op.drop_table("extra_practice_pool_items")
    op.drop_table("extra_practice_pools")
    op.drop_table("daily_practice_plan_items")
    op.drop_table("daily_practice_plans")
