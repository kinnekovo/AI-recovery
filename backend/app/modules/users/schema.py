from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.users.model import UserRole, UserStatus


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class PatientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    current_agent_id: UUID | None = None
    onboarding_status: str
    assessment_status: str
    training_status: str


class MeRead(BaseModel):
    user: UserRead
    patient_profile: PatientProfileRead | None = None
