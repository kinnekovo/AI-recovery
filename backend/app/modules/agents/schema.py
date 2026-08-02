from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relationship: str = Field(min_length=1, max_length=80)
    personality_style: str = Field(default="gentle", max_length=120)
    image_consent_confirmed: bool = True
    voice_consent_confirmed: bool = True


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    relationship: str
    personality_style: str
    avatar_file_id: UUID | None = None
    voice_sample_file_id: UUID | None = None
    welcome_audio_file_id: UUID | None = None
    voice_external_id: str | None = None
    generation_status: str
    image_consent_confirmed: bool
    voice_consent_confirmed: bool
    created_at: datetime


class AudioUrlResponse(BaseModel):
    audio_url: str
