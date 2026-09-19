import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

JSONDocument = JSON().with_variant(JSONB, "postgresql")


class PatientProfileSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "patient_profile_snapshots"
    __table_args__ = (
        UniqueConstraint("patient_profile_id", "evidence_fingerprint", name="uq_profile_snapshot_fingerprint"),
        Index("ix_profile_snapshot_latest", "patient_profile_id", "generated_at"),
    )
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    profile_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    as_of: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"))
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONDocument, nullable=False)


class ProfileEvidenceLink(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "profile_evidence_links"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "evaluation_run_id", "source_dimension_code", name="uq_profile_evidence_link"),
        Index("ix_profile_evidence_snapshot", "snapshot_id", "profile_dimension_code"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"), nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False)
    assessment_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="RESTRICT"))
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_dimension_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_dimension_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    metric_status: Mapped[str | None] = mapped_column(String(20))
    provider_version: Mapped[str | None] = mapped_column(String(120))
    canonical_result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_state: Mapped[str | None] = mapped_column(String(32))
    evidence_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_snapshot: Mapped[dict] = mapped_column(JSONDocument, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProfileBuildFailure(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profile_build_failures"
    __table_args__ = (UniqueConstraint("patient_profile_id", "input_fingerprint", name="uq_profile_build_failure_input"),)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[str] = mapped_column(String(80), nullable=False)
    retry_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=1)
    last_failed_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_retry_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    resolved_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profile_snapshots.id", ondelete="RESTRICT"))
