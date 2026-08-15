from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FamilyBoundPatientRead(BaseModel):
    binding_id: UUID
    patient_user_id: UUID
    patient_profile_id: UUID
    patient_username: str
    relationship_label: str
    status: str
    created_at: datetime
