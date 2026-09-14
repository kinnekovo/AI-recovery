from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AvatarVideoTaskRead(BaseModel):
    id: UUID
    status: str
    video_url: str | None = None
    error_message: str | None = None
    generation_ms: int | None = None
    created_at: datetime


class AvatarVideoTaskBrief(BaseModel):
    id: UUID
    status: str
