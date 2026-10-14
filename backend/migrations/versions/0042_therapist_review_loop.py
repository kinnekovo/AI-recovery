"""Therapist review workflow states and audit events.

Revision ID: 0042_therapist_review_loop
Revises: 0041_daily_practice_extra_pool
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0042_therapist_review_loop"
down_revision = "0041_daily_practice_extra_pool"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade():
    op.add_column("training_plan_exercise_rules", sa.Column("sequence_role", sa.String(24), nullable=True))
    op.add_column("training_plan_exercise_rules", sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True))
    op.execute("UPDATE training_plan_exercise_rules SET sequence_role = 'main' WHERE sequence_role IS NULL")
    op.execute("UPDATE training_plan_exercise_rules SET estimated_duration_seconds = 90 WHERE estimated_duration_seconds IS NULL")
    op.alter_column("training_plan_exercise_rules", "sequence_role", nullable=False, server_default="main")
    op.alter_column("training_plan_exercise_rules", "estimated_duration_seconds", nullable=False, server_default="90")
    op.drop_index("uq_attention_open_dedup", table_name="attention_items")
    op.create_index(
        "uq_attention_open_dedup",
        "attention_items",
        ["patient_profile_id", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged', 'in_review', 'waiting_information', 'waiting_plan_publish')"),
        sqlite_where=sa.text("status IN ('open', 'acknowledged', 'in_review', 'waiting_information', 'waiting_plan_publish')"),
    )
    op.add_column("attention_items", sa.Column("resolution_code", sa.String(64), nullable=True))
    op.add_column("attention_items", sa.Column("primary_evaluation_run_id", UUID, sa.ForeignKey("evaluation_runs.id"), nullable=True))
    op.add_column("attention_items", sa.Column("primary_stage_review_id", UUID, sa.ForeignKey("stage_reviews.id"), nullable=True))
    op.add_column("attention_items", sa.Column("waiting_reason", sa.String(64), nullable=True))
    op.add_column("attention_items", sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE attention_items SET status_updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) WHERE status_updated_at IS NULL")
    op.alter_column("attention_items", "status_updated_at", nullable=False, server_default=sa.func.now())

    op.create_table(
        "attention_item_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("attention_item_id", UUID, sa.ForeignKey("attention_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("related_refs", JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_attention_item_events_item_created", "attention_item_events", ["attention_item_id", "created_at"])
    op.create_index("ix_attention_item_events_actor_created", "attention_item_events", ["actor_user_id", "created_at"])

    op.add_column("stage_reviews", sa.Column("primary_attention_item_id", UUID, sa.ForeignKey("attention_items.id"), nullable=True))
    op.add_column("stage_reviews", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("stage_reviews", sa.Column("patient_context_snapshot", JSON, nullable=False, server_default=sa.text("'{}'")))
    op.add_column("stage_reviews", sa.Column("evidence_review_revision_ids", JSON, nullable=False, server_default=sa.text("'[]'")))
    op.add_column("stage_reviews", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stage_reviews", sa.Column("supersedes_review_id", UUID, sa.ForeignKey("stage_reviews.id"), nullable=True))
    op.add_column("therapist_decisions", sa.Column("attention_resolution_policy", sa.String(40), nullable=False, server_default="resolve"))
    op.add_column("therapist_decisions", sa.Column("expected_review_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("therapist_decisions", sa.Column("request_key", sa.String(64), nullable=True))
    op.create_index("uq_therapist_decision_review_request", "therapist_decisions", ["stage_review_id", "request_key"], unique=True, postgresql_where=sa.text("request_key IS NOT NULL"), sqlite_where=sa.text("request_key IS NOT NULL"))

    op.add_column("training_plan_versions", sa.Column("abandoned_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("training_plan_versions", sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_plan_versions", sa.Column("abandon_reason", sa.Text(), nullable=True))
    op.add_column("training_plan_versions", sa.Column("publish_request_key", sa.String(64), nullable=True))
    op.create_index("uq_training_plan_publish_request_key", "training_plan_versions", ["publish_request_key"], unique=True, postgresql_where=sa.text("publish_request_key IS NOT NULL"), sqlite_where=sa.text("publish_request_key IS NOT NULL"))
    op.add_column("evaluation_review_revisions", sa.Column("reason_code", sa.String(48), nullable=True))


def downgrade():
    op.drop_column("evaluation_review_revisions", "reason_code")
    op.drop_column("training_plan_exercise_rules", "estimated_duration_seconds")
    op.drop_column("training_plan_exercise_rules", "sequence_role")
    op.drop_index("uq_training_plan_publish_request_key", table_name="training_plan_versions")
    op.drop_column("training_plan_versions", "publish_request_key")
    op.drop_column("training_plan_versions", "abandon_reason")
    op.drop_column("training_plan_versions", "abandoned_at")
    op.drop_column("training_plan_versions", "abandoned_by_user_id")
    op.drop_index("uq_therapist_decision_review_request", table_name="therapist_decisions")
    op.drop_column("therapist_decisions", "request_key")
    op.drop_column("therapist_decisions", "expected_review_version")
    op.drop_column("therapist_decisions", "attention_resolution_policy")
    op.drop_column("stage_reviews", "supersedes_review_id")
    op.drop_column("stage_reviews", "ready_at")
    op.drop_column("stage_reviews", "evidence_review_revision_ids")
    op.drop_column("stage_reviews", "patient_context_snapshot")
    op.drop_column("stage_reviews", "primary_attention_item_id")
    op.drop_column("stage_reviews", "version")
    op.drop_index("ix_attention_item_events_actor_created", table_name="attention_item_events")
    op.drop_index("ix_attention_item_events_item_created", table_name="attention_item_events")
    op.drop_table("attention_item_events")
    op.drop_column("attention_items", "status_updated_at")
    op.drop_column("attention_items", "waiting_reason")
    op.drop_column("attention_items", "primary_stage_review_id")
    op.drop_column("attention_items", "primary_evaluation_run_id")
    op.drop_column("attention_items", "resolution_code")
    op.drop_index("uq_attention_open_dedup", table_name="attention_items")
    op.create_index(
        "uq_attention_open_dedup",
        "attention_items",
        ["patient_profile_id", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
        sqlite_where=sa.text("status IN ('open', 'acknowledged')"),
    )
