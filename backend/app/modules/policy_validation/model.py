import uuid
from sqlalchemy import ForeignKey,String,UniqueConstraint,JSON
from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import Mapped,mapped_column
from app.database.base import Base,UUIDPrimaryKeyMixin,TimestampMixin
J=JSON().with_variant(JSONB,"postgresql")
class PolicyValidationDataset(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="policy_validation_datasets";__table_args__=(UniqueConstraint("name","version",name="uq_policy_validation_dataset"),)
 name:Mapped[str]=mapped_column(String(160));version:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(16),default="draft");created_by_user_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=False)
class PolicyValidationDatasetItem(Base,UUIDPrimaryKeyMixin):
 __tablename__="policy_validation_dataset_items";__table_args__=(UniqueConstraint("dataset_id","policy_decision_id",name="uq_policy_validation_item"),)
 dataset_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"));policy_decision_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("policy_decisions.id",ondelete="RESTRICT"));snapshot:Mapped[dict]=mapped_column(J,default=dict)
class PolicyValidationRun(Base,UUIDPrimaryKeyMixin):
 __tablename__="policy_validation_runs"
 dataset_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"));policy_version:Mapped[str]=mapped_column(String(64));rules_version:Mapped[str]=mapped_column(String(64));validation_policy_version:Mapped[str]=mapped_column(String(64));input_fingerprint:Mapped[str]=mapped_column(String(64));report:Mapped[dict]=mapped_column(J);promotion_status:Mapped[str]=mapped_column(String(48));reason_codes:Mapped[list]=mapped_column(J,default=list)
class PolicyValidationRegistry(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="policy_validation_registry";__table_args__=(UniqueConstraint("policy_version","rules_version",name="uq_policy_validation_registry"),)
 policy_version:Mapped[str]=mapped_column(String(64));rules_version:Mapped[str]=mapped_column(String(64));validation_status:Mapped[str]=mapped_column(String(48));latest_validation_run_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey("policy_validation_runs.id",ondelete="RESTRICT"));status_reason_codes:Mapped[list]=mapped_column(J,default=list)
class PolicyValidationFailure(Base,UUIDPrimaryKeyMixin,TimestampMixin):
 __tablename__="policy_validation_failures";__table_args__=(UniqueConstraint("dataset_id","input_fingerprint",name="uq_policy_validation_failure"),)
 dataset_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"));input_fingerprint:Mapped[str]=mapped_column(String(64));failure_stage:Mapped[str]=mapped_column(String(80));error_code:Mapped[str]=mapped_column(String(80));retry_required:Mapped[bool]=mapped_column(default=True);retry_count:Mapped[int]=mapped_column(default=1)
