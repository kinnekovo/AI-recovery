from uuid import UUID

from pydantic import BaseModel


class AvatarSessionCreate(BaseModel):
    agent_id: UUID


class AvatarSessionRead(BaseModel):
    id: UUID
    session_id: str
    rtc_params: dict[str, object]
