from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScenarioDialogueCreate(BaseModel):
    session_task_id: UUID


class ScenarioDialogueHintRead(BaseModel):
    level: int
    text: str


class ScenarioDialoguePatientTurnCreate(BaseModel):
    transcript: str


class ScenarioDialogueTurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    turn_index: int
    speaker: str
    dialogue_act: str
    text: str
    audio_file_id: UUID | None = None
    created_at: datetime


class ScenarioDialogueRead(BaseModel):
    id: UUID
    status: str
    current_state: str
    patient_turn_count: int
    prompt_count: int
    maximum_prompt_level: int
    communication_goal: str
    turns: list[ScenarioDialogueTurnRead]


class ScenarioDialogueEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    goal_status: str
    goal_score: float
    information_score: float
    response_score: float
    relevance_score: float
    independence_score: float
    repair_score: float | None
    overall_score: float | None
    confidence: float
    review_status: str
    evidence_snapshot: dict
    scoring_version: str


class ScenarioDialogueReviewUpdate(BaseModel):
    evidence_overrides: dict = {}
    review_notes: str | None = None
    review_status: str = "confirmed"


class TherapistScenarioDialogueListItem(BaseModel):
    id: UUID
    created_at: datetime
    status: str
    current_state: str
    communication_goal: str
    patient_turn_count: int
    review_status: str | None = None
