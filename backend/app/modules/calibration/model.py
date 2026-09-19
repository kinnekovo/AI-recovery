import enum
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

class DatasetStatus(str,enum.Enum): draft="draft"; frozen="frozen"; archived="archived"
class MetricStatus(str,enum.Enum): experimental="experimental"; shadow="shadow"; provisional="provisional"; promoted="promoted"; suspended="suspended"

class CalibrationDataset(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="calibration_datasets"
 name:Mapped[str]=mapped_column(String(160),nullable=False); description:Mapped[str|None]=mapped_column(Text); version:Mapped[str]=mapped_column(String(64),nullable=False)
 status:Mapped[str]=mapped_column(String(16),default="draft",nullable=False); created_by_user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=False); frozen_at:Mapped[object|None]=mapped_column(DateTime(timezone=True))
 __table_args__=(UniqueConstraint("name","version",name="uq_calibration_dataset_name_version"),)
class CalibrationSample(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="calibration_samples"
 dataset_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("calibration_datasets.id",ondelete="RESTRICT"),nullable=False)
 patient_profile_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("patient_profiles.id",ondelete="RESTRICT"),nullable=False)
 evaluation_run_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("evaluation_runs.id",ondelete="RESTRICT"),nullable=False)
 dimension_code:Mapped[str]=mapped_column(String(100),nullable=False); automatic_value:Mapped[float|None]=mapped_column(nullable=True); automatic_status:Mapped[str]=mapped_column(String(32),nullable=False); unit:Mapped[str|None]=mapped_column(String(40)); task_type:Mapped[str|None]=mapped_column(String(40)); source_type:Mapped[str]=mapped_column(String(40),nullable=False); recorded_at:Mapped[object]=mapped_column(DateTime(timezone=True),nullable=False); metadata_snapshot:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
 __table_args__=(UniqueConstraint("dataset_id","evaluation_run_id","dimension_code",name="uq_calibration_sample_dimension"),)
class ReferenceAnnotation(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="reference_annotations"
 sample_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("calibration_samples.id",ondelete="RESTRICT"),nullable=False); annotator_user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False); annotation_round:Mapped[int]=mapped_column(Integer,default=1,nullable=False); dimension_code:Mapped[str]=mapped_column(String(100),nullable=False); value:Mapped[float|None]=mapped_column(nullable=True); unit:Mapped[str|None]=mapped_column(String(40)); confidence:Mapped[float|None]=mapped_column(nullable=True); comment:Mapped[str|None]=mapped_column(Text); supersedes_annotation_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey("reference_annotations.id",ondelete="RESTRICT")); is_adjudicated:Mapped[bool]=mapped_column(default=False,nullable=False)
 __table_args__=(UniqueConstraint("sample_id","annotator_user_id","annotation_round","dimension_code",name="uq_annotation_round"),)
class MetricRegistry(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="metric_registry"
 metric_code:Mapped[str]=mapped_column(String(120),unique=True,nullable=False); display_name:Mapped[str]=mapped_column(String(160),nullable=False); source:Mapped[str]=mapped_column(String(100),nullable=False); version:Mapped[str]=mapped_column(String(120),nullable=False); dimension_type:Mapped[str]=mapped_column(String(24),nullable=False); unit:Mapped[str|None]=mapped_column(String(40)); applicable_task_type:Mapped[str|None]=mapped_column(String(40)); status:Mapped[str]=mapped_column(String(20),default="experimental",nullable=False); last_calibrated_at:Mapped[object|None]=mapped_column(DateTime(timezone=True))
class CalibrationRun(Base,UUIDPrimaryKeyMixin):
 __tablename__="calibration_runs"
 dataset_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("calibration_datasets.id",ondelete="RESTRICT"),nullable=False); metric_registry_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("metric_registry.id",ondelete="RESTRICT"),nullable=False); created_by_user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False); split_snapshot:Mapped[dict]=mapped_column(JSONB,nullable=False); policy_snapshot:Mapped[dict]=mapped_column(JSONB,nullable=False); metrics_snapshot:Mapped[dict]=mapped_column(JSONB,nullable=False); promotion_decision:Mapped[str]=mapped_column(String(32),nullable=False); reason_codes:Mapped[list]=mapped_column(JSONB,default=list,nullable=False); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),default=utc_now,nullable=False)
