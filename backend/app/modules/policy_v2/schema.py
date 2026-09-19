from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class PolicyDecisionRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:UUID; patient_profile_id:UUID; profile_snapshot_id:UUID|None; policy_version:str; rules_version:str; mode:str; generated_at:datetime; status:str; input_fingerprint:str; decision_payload:dict; reason_codes:list; warnings:list
class PolicyFeedbackCreate(BaseModel):
 agreement:str=Field(pattern="^(agree|partially_agree|disagree|not_applicable)$"); reason_codes:list[str]=Field(default_factory=list); comment:str|None=None
class PolicyObservationCreate(BaseModel):
 training_session_id:UUID
