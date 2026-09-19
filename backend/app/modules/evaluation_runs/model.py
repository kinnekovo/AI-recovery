import enum
import uuid

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now


JSONDocument = JSON().with_variant(JSONB, "postgresql")


class EvaluationDomain(str, enum.Enum):
    repeat = "repeat"
    functional_communication = "functional_communication"
    clinical_stage = "clinical_stage"


class EvaluationSourceType(str, enum.Enum):
    attempt = "attempt"
    dialogue_session = "dialogue_session"
    assessment_session = "assessment_session"


class EvaluationResultStatus(str, enum.Enum):
    formal = "formal"
    provisional = "provisional"
    review_required = "review_required"
    unscorable = "unscorable"


class EvaluationAdoptionStatus(str, enum.Enum):
    candidate = "candidate"
    adopted = "adopted"
    superseded = "superseded"


class DimensionResultStatus(str, enum.Enum):
    measured = "measured"
    not_observed = "not_observed"
    unavailable = "unavailable"
    not_applicable = "not_applicable"


class ReviewAction(str, enum.Enum):
    confirmed = "confirmed"
    corrected = "corrected"
    unjudgeable = "unjudgeable"


class EvaluationRun(Base, UUIDPrimaryKeyMixin):
    """An append-only canonical evaluation result.

    `source_id` is intentionally polymorphic, so it cannot have one SQL foreign
    key.  Creation validates the source ownership and preserves an immutable
    `input_provenance` snapshot before the source can later change.
    """

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('repeat', 'functional_communication', 'clinical_stage')",
            name="ck_evaluation_runs_domain",
        ),
        CheckConstraint(
            "source_type IN ('attempt', 'dialogue_session', 'assessment_session')",
            name="ck_evaluation_runs_source_type",
        ),
        CheckConstraint(
            "result_status IN ('formal', 'provisional', 'review_required', 'unscorable')",
            name="ck_evaluation_runs_result_status",
        ),
        CheckConstraint(
            "adoption_status IN ('candidate', 'adopted', 'superseded')",
            name="ck_evaluation_runs_adoption_status",
        ),
        Index("ix_evaluation_runs_source_domain", "source_type", "source_id", "domain"),
        Index(
            "uq_evaluation_runs_one_adopted_source_domain",
            "source_type",
            "source_id",
            "domain",
            unique=True,
            postgresql_where=text("adoption_status = 'adopted'"),
            sqlite_where=text("adoption_status = 'adopted'"),
        ),
    )

    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    domain: Mapped[EvaluationDomain] = mapped_column(String(40), nullable=False)
    source_type: Mapped[EvaluationSourceType] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    config_snapshot: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    input_provenance: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    quality_gate: Mapped[dict] = mapped_column(JSONDocument, nullable=False)
    result_status: Mapped[EvaluationResultStatus] = mapped_column(String(32), nullable=False)
    profile_eligibility: Mapped[bool] = mapped_column(nullable=False)
    profile_ineligibility_reasons: Mapped[list[str]] = mapped_column(JSONDocument, default=list, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONDocument, default=list, nullable=False)
    adoption_status: Mapped[EvaluationAdoptionStatus] = mapped_column(
        String(20), default=EvaluationAdoptionStatus.candidate.value, nullable=False
    )
    supersedes_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    dimension_results: Mapped[list["EvaluationDimensionResult"]] = relationship(
        back_populates="evaluation_run", cascade="save-update, merge"
    )
    review_revisions: Mapped[list["EvaluationReviewRevision"]] = relationship(
        back_populates="evaluation_run",
        foreign_keys="EvaluationReviewRevision.evaluation_run_id",
        cascade="save-update, merge",
    )


class EvaluationDimensionResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evaluation_dimension_results"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "dimension_code", name="uq_evaluation_dimension_run_code"),
        CheckConstraint(
            "status IN ('measured', 'not_observed', 'unavailable', 'not_applicable')",
            name="ck_evaluation_dimension_results_status",
        ),
        Index("ix_evaluation_dimension_results_run_dimension", "evaluation_run_id", "dimension_code"),
    )

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    dimension_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[DimensionResultStatus] = mapped_column(String(32), nullable=False)
    measurement_quality: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    evidence_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONDocument, default=list, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="dimension_results")


class EvaluationReviewRevision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evaluation_review_revisions"

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    dimension_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_dimension_results.id", ondelete="SET NULL"), nullable=True
    )
    review_action: Mapped[ReviewAction] = mapped_column(String(32), nullable=False)
    automatic_value_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    revised_value_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    evidence_override: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recomputed_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    evaluation_run: Mapped[EvaluationRun] = relationship(
        back_populates="review_revisions", foreign_keys=[evaluation_run_id]
    )
