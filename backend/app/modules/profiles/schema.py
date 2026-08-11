from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AbilityProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_profile_id: UUID
    current_content_level: str
    current_autonomy_level: str
    avg_script_accuracy_recent: float | None = None
    avg_error_count_recent: float | None = None
    avg_speech_rate_recent: float | None = None
    avg_loudness_recent: float | None = None
    assessment_summary: str
    recommendation: str
    confidence: float
    evidence: dict
    updated_at: datetime
