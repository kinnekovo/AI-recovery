from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class ProposalCreate(BaseModel):
    action_type: str = Field(pattern="^(training_focus_override|difficulty_step_adjustment)$")
    target_training_session_id: UUID

class ApprovalCreate(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)

class RejectionCreate(BaseModel):
    reason_code: str = Field(default="therapist_rejected", max_length=80)
    comment: str | None = Field(default=None, max_length=2000)

class ObservationCreate(BaseModel):
    outcome: str = Field(pattern="^(session_completed|session_abandoned|therapist_accepted|rollback_requested)$")
    therapist_feedback: str | None = Field(default=None, max_length=2000)

class RollbackCreate(BaseModel):
    reason_code: str = Field(min_length=1, max_length=80)
    comment: str | None = Field(default=None, max_length=2000)

class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; policy_decision_id: UUID; patient_profile_id: UUID; target_training_session_id: UUID
    action_type: str; proposed_value: dict; current_value: dict; expected_scope: dict; reason_codes: list
    policy_version: str; rules_version: str; validation_run_id: UUID | None; profile_snapshot_id: UUID | None
    activation_policy_version: str; status: str; expires_at: datetime; created_at: datetime
