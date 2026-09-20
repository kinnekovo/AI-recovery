"""Product Reset v1 domain foundation.

Revision ID: 0040_product_reset_v1
Revises: 0039_controlled_governance
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0040_product_reset_v1"
down_revision = "0039_controlled_governance"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    op.add_column("patient_profiles", sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"))

    op.create_table(
        "rehabilitation_goals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_rehabilitation_goals_patient_profile_id", "rehabilitation_goals", ["patient_profile_id"])
    op.create_index(
        "uq_rehabilitation_goal_active_primary",
        "rehabilitation_goals",
        ["patient_profile_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND is_primary = true"),
    )

    op.create_table(
        "training_plan_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("rehabilitation_goal_id", UUID, sa.ForeignKey("rehabilitation_goals.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("stage_focus", sa.String(160), nullable=False),
        sa.Column("strategy_snapshot", JSON, nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("published_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_id", UUID, sa.ForeignKey("training_plan_versions.id"), nullable=True),
        sa.Column("source_decision_id", UUID, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("patient_profile_id", "version_number", name="uq_training_plan_patient_version"),
    )
    op.create_index("ix_training_plan_versions_patient_profile_id", "training_plan_versions", ["patient_profile_id"])
    op.create_index("ix_training_plan_versions_rehabilitation_goal_id", "training_plan_versions", ["rehabilitation_goal_id"])
    op.create_index(
        "uq_training_plan_active_patient",
        "training_plan_versions",
        ["patient_profile_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "training_plan_exercise_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("training_plan_version_id", UUID, sa.ForeignKey("training_plan_versions.id"), nullable=False),
        sa.Column("task_template_id", UUID, sa.ForeignKey("task_templates.id"), nullable=False),
        sa.Column("exercise_type", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("target_repetitions", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("max_information_units", sa.Integer(), nullable=True),
        sa.Column("prompt_policy", JSON, nullable=False),
        sa.Column("scene_scope", JSON, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("training_plan_version_id", "order_index", name="uq_plan_rule_order"),
    )
    op.create_index("ix_training_plan_exercise_rules_training_plan_version_id", "training_plan_exercise_rules", ["training_plan_version_id"])

    op.add_column("training_sessions", sa.Column("formal_training_plan_version_id", UUID, nullable=True))
    op.create_foreign_key("fk_training_session_formal_plan", "training_sessions", "training_plan_versions", ["formal_training_plan_version_id"], ["id"])
    op.create_index("ix_training_sessions_formal_training_plan_version_id", "training_sessions", ["formal_training_plan_version_id"])
    op.add_column("training_sessions", sa.Column("session_kind", sa.String(24), nullable=False, server_default="legacy"))
    op.add_column("training_sessions", sa.Column("v2_status", sa.String(24), nullable=False, server_default="in_progress"))
    op.add_column("training_sessions", sa.Column("local_session_date", sa.Date(), nullable=True))
    op.add_column("training_sessions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_sessions", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_sessions", sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_sessions", sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("training_sessions", sa.Column("summary_status", sa.String(24), nullable=False, server_default="pending"))
    op.add_column("training_sessions", sa.Column("technical_status", sa.String(32), nullable=False, server_default="ready"))
    op.create_index(
        "uq_formal_daily_session",
        "training_sessions",
        ["patient_profile_id", "formal_training_plan_version_id", "local_session_date"],
        unique=True,
        postgresql_where=sa.text("session_kind = 'formal'"),
    )

    for name, column in (
        ("v2_status", sa.Column("v2_status", sa.String(24), nullable=False, server_default="in_progress")),
        ("content_snapshot", sa.Column("content_snapshot", JSON, nullable=False, server_default=sa.text("'{}'::jsonb"))),
        ("instruction_snapshot", sa.Column("instruction_snapshot", sa.Text(), nullable=True)),
        ("target_snapshot", sa.Column("target_snapshot", sa.Text(), nullable=True)),
        ("exercise_type_snapshot", sa.Column("exercise_type_snapshot", sa.String(32), nullable=True)),
        ("difficulty_snapshot", sa.Column("difficulty_snapshot", sa.String(32), nullable=True)),
        ("max_information_units_snapshot", sa.Column("max_information_units_snapshot", sa.Integer(), nullable=True)),
        ("prompt_policy_snapshot", sa.Column("prompt_policy_snapshot", JSON, nullable=False, server_default=sa.text("'{}'::jsonb"))),
        ("contract_version_snapshot", sa.Column("contract_version_snapshot", sa.String(80), nullable=True)),
    ):
        op.add_column("session_tasks", column)

    op.add_column("attempts", sa.Column("terminal_state", sa.String(24), nullable=False, server_default="pending"))
    op.add_column("attempts", sa.Column("technical_validity", sa.String(32), nullable=False, server_default="unknown"))
    op.add_column("attempts", sa.Column("measurement_eligibility", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("attempts", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "clinical_evidence",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("training_session_id", UUID, sa.ForeignKey("training_sessions.id"), nullable=True),
        sa.Column("evidence_type", sa.String(48), nullable=False),
        sa.Column("source_type", sa.String(48), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("source_status", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("provider_version", sa.String(120), nullable=True),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("source_type", "source_id", "evidence_type", name="uq_evidence_source_type"),
    )
    op.create_index("ix_clinical_evidence_patient_profile_id", "clinical_evidence", ["patient_profile_id"])
    op.create_index("ix_clinical_evidence_training_session_id", "clinical_evidence", ["training_session_id"])

    op.create_table(
        "clinical_metrics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("training_session_id", UUID, sa.ForeignKey("training_sessions.id"), nullable=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measurement_context", JSON, nullable=False),
        sa.Column("source_type", sa.String(48), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("algorithm", sa.String(120), nullable=True),
        sa.Column("instrument", sa.String(120), nullable=True),
        sa.Column("version", sa.String(80), nullable=True),
        sa.Column("quality", JSON, nullable=False),
        sa.Column("evidence_ids", JSON, nullable=False),
        sa.Column("comparison_key", sa.String(255), nullable=True),
        sa.Column("decision_eligible", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("source_type", "source_id", "code", name="uq_metric_source_code"),
    )
    op.create_index("ix_clinical_metrics_patient_profile_id", "clinical_metrics", ["patient_profile_id"])
    op.create_index("ix_clinical_metrics_training_session_id", "clinical_metrics", ["training_session_id"])
    op.create_index("ix_clinical_metrics_code", "clinical_metrics", ["code"])
    op.create_index("ix_clinical_metrics_comparison_key", "clinical_metrics", ["comparison_key"])

    op.create_table(
        "clinical_observations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(48), nullable=False),
        sa.Column("time_window", JSON, nullable=False),
        sa.Column("supporting_metric_ids", JSON, nullable=False),
        sa.Column("supporting_evidence_ids", JSON, nullable=False),
        sa.Column("generator", sa.String(24), nullable=False),
        sa.Column("generator_version", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("limitations", JSON, nullable=False),
        sa.Column("source_status", sa.String(24), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_clinical_observations_patient_profile_id", "clinical_observations", ["patient_profile_id"])

    op.create_table(
        "clinical_recommendations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("scope", sa.String(48), nullable=False),
        sa.Column("candidate_action", sa.Text(), nullable=False),
        sa.Column("basis_observation_ids", JSON, nullable=False),
        sa.Column("generator", sa.String(24), nullable=False),
        sa.Column("generator_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_status", sa.String(24), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_clinical_recommendations_patient_profile_id", "clinical_recommendations", ["patient_profile_id"])

    op.create_table(
        "patient_milestones",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.String(180), nullable=False),
        sa.Column("trigger_facts", JSON, nullable=False),
        sa.Column("evidence_ids", JSON, nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("patient_profile_id", "dedup_key", name="uq_patient_milestone_dedup"),
    )
    op.create_index("ix_patient_milestones_patient_profile_id", "patient_milestones", ["patient_profile_id"])

    op.create_table(
        "attention_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("trigger_code", sa.String(80), nullable=False),
        sa.Column("trigger_facts", JSON, nullable=False),
        sa.Column("source_refs", JSON, nullable=False),
        sa.Column("evidence_ids", JSON, nullable=False),
        sa.Column("dedup_key", sa.String(180), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("assigned_to_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_attention_items_patient_profile_id", "attention_items", ["patient_profile_id"])
    op.create_index("ix_attention_items_item_type", "attention_items", ["item_type"])
    op.create_index(
        "uq_attention_open_dedup", "attention_items", ["patient_profile_id", "dedup_key"], unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
    )

    op.create_table(
        "stage_reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("training_plan_version_id", UUID, sa.ForeignKey("training_plan_versions.id"), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("review_window", JSON, nullable=False),
        sa.Column("facts_snapshot", JSON, nullable=False),
        sa.Column("observation_ids", JSON, nullable=False),
        sa.Column("recommendation_ids", JSON, nullable=False),
        sa.Column("attention_item_ids", JSON, nullable=False),
        sa.Column("assessment_ids", JSON, nullable=False),
        sa.Column("clinical_stage_run_ids", JSON, nullable=False),
        sa.Column("therapist_notes", sa.Text(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_stage_reviews_patient_profile_id", "stage_reviews", ["patient_profile_id"])

    op.create_table(
        "therapist_decisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("stage_review_id", UUID, sa.ForeignKey("stage_reviews.id"), nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision_type", sa.String(48), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_attention_item_id", UUID, sa.ForeignKey("attention_items.id"), nullable=True),
        sa.Column("payload_snapshot", JSON, nullable=False),
        sa.Column("result_snapshot", JSON, nullable=False),
        sa.Column("resulting_training_plan_version_id", UUID, sa.ForeignKey("training_plan_versions.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_therapist_decisions_patient_profile_id", "therapist_decisions", ["patient_profile_id"])
    op.create_index("ix_therapist_decisions_stage_review_id", "therapist_decisions", ["stage_review_id"])

    op.create_table(
        "training_session_summaries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("training_session_id", UUID, sa.ForeignKey("training_sessions.id"), nullable=False),
        sa.Column("patient_profile_id", UUID, sa.ForeignKey("patient_profiles.id"), nullable=False),
        sa.Column("facts", JSON, nullable=False),
        sa.Column("patient_observations", JSON, nullable=False),
        sa.Column("comparison_to_previous", JSON, nullable=False),
        sa.Column("next_training_focus", sa.Text(), nullable=False),
        sa.Column("generation_method", sa.String(32), nullable=False),
        sa.Column("source_status", sa.String(24), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("training_session_id", name="uq_training_session_summary"),
    )
    op.create_index("ix_training_session_summaries_patient_profile_id", "training_session_summaries", ["patient_profile_id"])


def downgrade():
    op.drop_table("training_session_summaries")
    op.drop_table("therapist_decisions")
    op.drop_table("stage_reviews")
    op.drop_table("attention_items")
    op.drop_table("patient_milestones")
    op.drop_table("clinical_recommendations")
    op.drop_table("clinical_observations")
    op.drop_table("clinical_metrics")
    op.drop_table("clinical_evidence")
    for column in ("completed_at", "measurement_eligibility", "technical_validity", "terminal_state"):
        op.drop_column("attempts", column)
    for column in (
        "contract_version_snapshot", "prompt_policy_snapshot", "max_information_units_snapshot",
        "difficulty_snapshot", "exercise_type_snapshot", "target_snapshot", "instruction_snapshot",
        "content_snapshot", "v2_status",
    ):
        op.drop_column("session_tasks", column)
    op.drop_index("uq_formal_daily_session", table_name="training_sessions")
    for column in (
        "technical_status", "summary_status", "aborted_at", "completed_at", "resumed_at", "paused_at",
        "started_at", "local_session_date", "v2_status", "session_kind",
    ):
        op.drop_column("training_sessions", column)
    op.drop_index("ix_training_sessions_formal_training_plan_version_id", table_name="training_sessions")
    op.drop_constraint("fk_training_session_formal_plan", "training_sessions", type_="foreignkey")
    op.drop_column("training_sessions", "formal_training_plan_version_id")
    op.drop_table("training_plan_exercise_rules")
    op.drop_table("training_plan_versions")
    op.drop_table("rehabilitation_goals")
    op.drop_column("patient_profiles", "timezone")

