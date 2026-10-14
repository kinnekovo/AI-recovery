import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


JSONDocument = JSON().with_variant(JSONB, "postgresql")


class RehabilitationGoal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rehabilitation_goals"
    __table_args__ = (
        Index(
            "uq_rehabilitation_goal_active_primary",
            "patient_profile_id",
            unique=True,
            postgresql_where=text("status = 'active' AND is_primary = true"),
            sqlite_where=text("status = 'active' AND is_primary = 1"),
        ),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class TrainingPlanVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_plan_versions"
    __table_args__ = (
        UniqueConstraint("patient_profile_id", "version_number", name="uq_training_plan_patient_version"),
        Index(
            "uq_training_plan_active_patient",
            "patient_profile_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index(
            "uq_training_plan_publish_request_key",
            "publish_request_key",
            unique=True,
            postgresql_where=text("publish_request_key IS NOT NULL"),
            sqlite_where=text("publish_request_key IS NOT NULL"),
        ),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    rehabilitation_goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rehabilitation_goals.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    stage_focus: Mapped[str] = mapped_column(String(160), nullable=False)
    strategy_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plan_versions.id"), nullable=True)
    source_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    abandoned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandon_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_request_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    exercise_rules: Mapped[list["TrainingPlanExerciseRule"]] = relationship(
        back_populates="plan_version", cascade="all, delete-orphan", order_by="TrainingPlanExerciseRule.order_index"
    )


class TrainingPlanExerciseRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_plan_exercise_rules"
    __table_args__ = (UniqueConstraint("training_plan_version_id", "order_index", name="uq_plan_rule_order"),)

    training_plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plan_versions.id"), index=True)
    task_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_templates.id"), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_role: Mapped[str] = mapped_column(String(24), default="main", nullable=False)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    target_repetitions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    max_information_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_policy: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    scene_scope: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)

    plan_version: Mapped[TrainingPlanVersion] = relationship(back_populates="exercise_rules")
    task_template = relationship("TaskTemplate")


class DailyPracticePlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A stable, date-scoped execution plan derived from the therapist plan."""

    __tablename__ = "daily_practice_plans"
    __table_args__ = (
        UniqueConstraint("patient_profile_id", "local_date", "version_number", name="uq_daily_practice_plan_version"),
        Index("ix_daily_practice_plans_patient_date", "patient_profile_id", "local_date"),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="system", nullable=False)
    training_plan_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plan_versions.id"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(80), default="daily-practice-v1", nullable=False)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generation_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["DailyPracticePlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="DailyPracticePlanItem.order_index"
    )


class DailyPracticePlanItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "daily_practice_plan_items"
    __table_args__ = (UniqueConstraint("daily_plan_id", "order_index", name="uq_daily_plan_item_order"),)

    daily_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("daily_practice_plans.id"), index=True)
    task_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_templates.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_role: Mapped[str] = mapped_column(String(24), default="main", nullable=False)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    selection_source: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    therapist_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    difficulty_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)

    plan: Mapped[DailyPracticePlan] = relationship(back_populates="items")
    task_template = relationship("TaskTemplate")


class ExtraPracticePool(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "extra_practice_pools"
    __table_args__ = (UniqueConstraint("patient_profile_id", "local_date", "version_number", name="uq_extra_pool_version"),)

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), default="extra-pool-v1", nullable=False)
    generation_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    refreshed_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["ExtraPracticePoolItem"]] = relationship(
        back_populates="pool", cascade="all, delete-orphan", order_by="ExtraPracticePoolItem.order_index"
    )


class ExtraPracticePoolItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "extra_practice_pool_items"
    __table_args__ = (UniqueConstraint("pool_id", "task_template_id", name="uq_extra_pool_task"),)

    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("extra_practice_pools.id"), index=True)
    task_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("task_templates.id"), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_source: Mapped[str] = mapped_column(String(32), nullable=False)
    display_reason: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)

    pool: Mapped[ExtraPracticePool] = relationship(back_populates="items")
    task_template = relationship("TaskTemplate")


class EvidenceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clinical_evidence"
    __table_args__ = (UniqueConstraint("source_type", "source_id", "evidence_type", name="uq_evidence_source_type"),)

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    training_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_status: Mapped[str] = mapped_column(String(24), default="real", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MetricRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clinical_metrics"
    __table_args__ = (UniqueConstraint("source_type", "source_id", "code", name="uq_metric_source_code"),)

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    training_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    measurement_context: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    algorithm: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quality: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    comparison_key: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    decision_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ObservationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clinical_observations"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(48), nullable=False)
    time_window: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    supporting_metric_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    supporting_evidence_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    generator: Mapped[str] = mapped_column(String(24), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    limitations: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    source_status: Mapped[str] = mapped_column(String(24), default="real", nullable=False)


class RecommendationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clinical_recommendations"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    scope: Mapped[str] = mapped_column(String(48), nullable=False)
    candidate_action: Mapped[str] = mapped_column(Text, nullable=False)
    basis_observation_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    generator: Mapped[str] = mapped_column(String(24), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="proposed", nullable=False)
    source_status: Mapped[str] = mapped_column(String(24), default="real", nullable=False)


class Milestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patient_milestones"
    __table_args__ = (UniqueConstraint("patient_profile_id", "dedup_key", name="uq_patient_milestone_dedup"),)

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(180), nullable=False)
    trigger_facts: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AttentionItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attention_items"
    __table_args__ = (
        Index(
            "uq_attention_open_dedup",
            "patient_profile_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged', 'in_review', 'waiting_information', 'waiting_plan_publish')"),
            sqlite_where=text("status IN ('open', 'acknowledged', 'in_review', 'waiting_information', 'waiting_plan_publish')"),
        ),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    trigger_code: Mapped[str] = mapped_column(String(80), nullable=False)
    trigger_facts: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(180), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id"), nullable=True)
    primary_stage_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stage_reviews.id"), nullable=True)
    waiting_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class StageReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "stage_reviews"

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    training_plan_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plan_versions.id"), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_window: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    facts_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    observation_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    recommendation_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    attention_item_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    assessment_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    clinical_stage_run_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    therapist_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    primary_attention_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attention_items.id"), nullable=True)
    patient_context_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    evidence_review_revision_ids: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stage_reviews.id"), nullable=True)


class TherapistDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "therapist_decisions"
    __table_args__ = (
        Index(
            "uq_therapist_decision_review_request",
            "stage_review_id",
            "request_key",
            unique=True,
            postgresql_where=text("request_key IS NOT NULL"),
            sqlite_where=text("request_key IS NOT NULL"),
        ),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    stage_review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stage_reviews.id"), index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_attention_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attention_items.id"), nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    result_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    resulting_training_plan_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_plan_versions.id"), nullable=True)
    attention_resolution_policy: Mapped[str] = mapped_column(String(40), default="resolve", nullable=False)
    expected_review_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TrainingSessionSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "training_session_summaries"
    __table_args__ = (UniqueConstraint("training_session_id", name="uq_training_session_summary"),)

    training_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True)
    facts: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    patient_observations: Mapped[list] = mapped_column(JSONDocument, default=list, nullable=False)
    comparison_to_previous: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    next_training_focus: Mapped[str] = mapped_column(Text, nullable=False)
    generation_method: Mapped[str] = mapped_column(String(32), default="deterministic_template", nullable=False)
    source_status: Mapped[str] = mapped_column(String(24), default="real", nullable=False)
