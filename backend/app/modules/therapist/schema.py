from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TherapistPatientRead(BaseModel):
    user_id: UUID
    patient_profile_id: UUID
    username: str
    assessment_status: str
    training_status: str
    pending_review_count: int = 0
    latest_assessment_at: datetime | None = None
    created_at: datetime
