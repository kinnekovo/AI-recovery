from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttemptCreate(BaseModel):
    session_task_id: UUID
    prompt_level: int = 0
    start_latency_ms: int | None = None
    duration_ms: int | None = None
    skipped: bool = False
    requested_help: bool = False


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_task_id: UUID
    attempt_no: int
    audio_file_id: UUID | None = None
    prompt_level: int
    duration_ms: int | None = None
    skipped: bool
    requested_help: bool
    audio_quality: str | None = None
    analysis_error_code: str | None = None
    analysis_error_message: str | None = None
    analysis_status: str
    created_at: datetime
