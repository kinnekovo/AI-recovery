from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.files.model import FileType


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_type: FileType
    original_name: str
    storage_path: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime


class UploadResponse(BaseModel):
    file: FileRead
    url: str
