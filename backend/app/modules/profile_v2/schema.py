from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class ProfileSnapshotRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; patient_profile_id: UUID; profile_schema_version: str; mapping_version: str; evidence_policy_version: str
    generated_at: datetime; as_of: datetime|None; status: str; previous_snapshot_id: UUID|None; evidence_fingerprint: str; payload: dict

class ProfileEvidenceLinkRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; snapshot_id: UUID; evaluation_run_id: UUID; source_type: str; source_id: UUID; profile_dimension_code: str
    source_dimension_code: str; source_kind: str; unit: str|None; metric_status: str|None; canonical_result_status: str; evidence_timestamp: datetime; metadata_snapshot: dict
