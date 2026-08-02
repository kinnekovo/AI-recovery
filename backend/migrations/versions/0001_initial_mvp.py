"""initial mvp schema

Revision ID: 0001_initial_mvp
Revises:
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_mvp"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("patient", "family", "admin", name="user_role")
    user_status = sa.Enum("active", "disabled", name="user_status")
    onboarding_status = sa.Enum("pending_agent", "ready", name="onboarding_status")
    file_type = sa.Enum("agent_image", "voice_sample", "training_audio", "generated_audio", name="file_type")
    file_status = sa.Enum("active", "deleted", name="file_status")
    consent_status = sa.Enum("confirmed", "revoked", name="consent_status")
    agent_status = sa.Enum("draft", "voice_ready", "ready", "failed", name="agent_generation_status")
    training_type = sa.Enum("repeat", "scenario", name="training_type")
    plan_status = sa.Enum("planned", "in_progress", "completed", name="training_status_enum")
    item_status = sa.Enum("planned", "in_progress", "completed", name="training_item_status")
    session_training_type = sa.Enum("repeat", "scenario", name="session_training_type")
    session_status = sa.Enum("planned", "in_progress", "completed", name="session_status")
    session_task_status = sa.Enum("planned", "in_progress", "completed", name="session_task_status")
    analysis_status = sa.Enum("pending", "completed", "failed", name="analysis_status")

    op.create_table(
        "users",
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "patient_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("onboarding_status", onboarding_status, nullable=False),
        sa.Column("assessment_status", sa.String(length=40), nullable=False),
        sa.Column("training_status", sa.String(length=40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "files",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_type", file_type, nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=600), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", file_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agents",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("relationship", sa.String(length=80), nullable=False),
        sa.Column("personality_style", sa.String(length=120), nullable=False),
        sa.Column("avatar_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voice_sample_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("welcome_audio_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voice_external_id", sa.String(length=160), nullable=True),
        sa.Column("generation_status", agent_status, nullable=False),
        sa.Column("image_consent_confirmed", sa.Boolean(), nullable=False),
        sa.Column("voice_consent_confirmed", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["avatar_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.ForeignKeyConstraint(["voice_sample_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["welcome_audio_file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agents_patient_profile_id"), "agents", ["patient_profile_id"], unique=False)
    op.create_foreign_key(
        "fk_patient_profiles_current_agent_id_agents", "patient_profiles", "agents", ["current_agent_id"], ["id"]
    )

    op.create_table(
        "consents",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type", sa.String(length=40), nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("consent_status", consent_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "task_templates",
        sa.Column("task_type", training_type, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("target_text", sa.Text(), nullable=False),
        sa.Column("content_level", sa.String(length=8), nullable=False),
        sa.Column("autonomy_level", sa.String(length=8), nullable=False),
        sa.Column("scene_prompt", sa.Text(), nullable=True),
        sa.Column("scoring_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "training_plans",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_plans_patient_profile_id"), "training_plans", ["patient_profile_id"])

    op.create_table(
        "training_plan_items",
        sa.Column("training_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", item_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.ForeignKeyConstraint(["training_plan_id"], ["training_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_plan_items_training_plan_id"), "training_plan_items", ["training_plan_id"])

    op.create_table(
        "training_sessions",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("training_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("training_type", session_training_type, nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.ForeignKeyConstraint(["training_plan_id"], ["training_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_sessions_patient_profile_id"), "training_sessions", ["patient_profile_id"])

    op.create_table(
        "session_tasks",
        sa.Column("training_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("training_plan_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("prompt_level", sa.Integer(), nullable=False),
        sa.Column("status", session_task_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_template_id"], ["task_templates.id"]),
        sa.ForeignKeyConstraint(["training_plan_item_id"], ["training_plan_items.id"]),
        sa.ForeignKeyConstraint(["training_session_id"], ["training_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_tasks_training_session_id"), "session_tasks", ["training_session_id"])

    op.create_table(
        "attempts",
        sa.Column("session_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("audio_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_level", sa.Integer(), nullable=False),
        sa.Column("start_latency_ms", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("requested_help", sa.Boolean(), nullable=False),
        sa.Column("audio_quality", sa.String(), nullable=True),
        sa.Column("analysis_status", analysis_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audio_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["session_task_id"], ["session_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attempts_session_task_id"), "attempts", ["session_task_id"])

    op.create_table(
        "attempt_analysis_results",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asr_text", sa.Text(), nullable=False),
        sa.Column("acoustic_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("semantic_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_model_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider_version", sa.String(length=80), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
    )

    op.create_table(
        "attempt_scores",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("content_score", sa.Integer(), nullable=False),
        sa.Column("clarity_score", sa.Integer(), nullable=False),
        sa.Column("fluency_score", sa.Integer(), nullable=False),
        sa.Column("loudness_score", sa.Integer(), nullable=False),
        sa.Column("prompt_dependence_score", sa.Integer(), nullable=False),
        sa.Column("main_strength", sa.String(length=255), nullable=False),
        sa.Column("main_issue", sa.String(length=255), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
    )


def downgrade() -> None:
    op.drop_table("attempt_scores")
    op.drop_table("attempt_analysis_results")
    op.drop_index(op.f("ix_attempts_session_task_id"), table_name="attempts")
    op.drop_table("attempts")
    op.drop_index(op.f("ix_session_tasks_training_session_id"), table_name="session_tasks")
    op.drop_table("session_tasks")
    op.drop_index(op.f("ix_training_sessions_patient_profile_id"), table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index(op.f("ix_training_plan_items_training_plan_id"), table_name="training_plan_items")
    op.drop_table("training_plan_items")
    op.drop_index(op.f("ix_training_plans_patient_profile_id"), table_name="training_plans")
    op.drop_table("training_plans")
    op.drop_table("task_templates")
    op.drop_table("consents")
    op.drop_constraint("fk_patient_profiles_current_agent_id_agents", "patient_profiles", type_="foreignkey")
    op.drop_index(op.f("ix_agents_patient_profile_id"), table_name="agents")
    op.drop_table("agents")
    op.drop_table("files")
    op.drop_table("patient_profiles")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")

    for name in [
        "analysis_status",
        "session_task_status",
        "session_status",
        "session_training_type",
        "training_item_status",
        "training_status_enum",
        "training_type",
        "agent_generation_status",
        "consent_status",
        "file_status",
        "file_type",
        "onboarding_status",
        "user_status",
        "user_role",
    ]:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
