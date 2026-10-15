from uuid import UUID

from pydantic import BaseModel, Field


class AvatarSessionCreate(BaseModel):
    agent_id: UUID | None = None
    provider: str = "aliyun"


class AvatarSpeechCreate(BaseModel):
    agent_id: UUID | None = None
    text: str = Field(min_length=1, max_length=150)


class AvatarSessionRead(BaseModel):
    id: UUID
    session_id: str
    rtc_params: dict[str, object]
