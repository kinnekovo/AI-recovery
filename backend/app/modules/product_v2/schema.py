from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GoalCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    effective_from: date | None = None
    effective_to: date | None = None
    is_primary: bool = True


class ExerciseRuleCreate(BaseModel):
    task_template_id: UUID
    exercise_type: Literal["repeat", "scenario"]
    order_index: int = Field(ge=0)
    target_repetitions: int = Field(default=1, ge=1, le=20)
    difficulty: str = Field(default="standard", min_length=1, max_length=32)
    max_information_units: int | None = Field(default=None, ge=1, le=20)
    prompt_policy: dict = Field(default_factory=dict)
    scene_scope: dict = Field(default_factory=dict)


class TrainingPlanDraftCreate(BaseModel):
    rehabilitation_goal_id: UUID
    stage_focus: str = Field(min_length=1, max_length=160)
    frequency: str = Field(default="daily", max_length=80)
    duration_minutes: int = Field(default=15, ge=1, le=180)
    forms: list[str] = Field(default_factory=list)
    scene_scope: list[str] = Field(default_factory=list)
    difficulty: str = Field(default="standard", max_length=32)
    max_information_units: int | None = Field(default=None, ge=1, le=20)
    prompt_policy: dict = Field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None
    supersedes_id: UUID | None = None
    exercise_rules: list[ExerciseRuleCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_order(self):
        orders = [item.order_index for item in self.exercise_rules]
        if len(orders) != len(set(orders)):
            raise ValueError("exercise rule order_index must be unique")
        return self


class SessionStart(BaseModel):
    session_kind: Literal["formal", "extra_practice"] = "formal"
    training_plan_version_id: UUID | None = None


class SessionCommand(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AttemptCreateV2(BaseModel):
    session_task_id: UUID
    prompt_level: int = Field(default=0, ge=0, le=3)
    start_latency_ms: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)


class PatientSettingsUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class AttentionResolve(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=2000)
    status: Literal["resolved", "dismissed"] = "resolved"


class StageReviewCreate(BaseModel):
    review_from: datetime | None = None
    review_to: datetime | None = None
    therapist_notes: str | None = Field(default=None, max_length=5000)


class DecisionCreate(BaseModel):
    decision_type: Literal[
        "continue_current_plan",
        "adjust_stage_focus",
        "adjust_strategy",
        "request_formal_assessment",
        "create_new_training_plan_version",
        "no_action",
        "add_clinical_note",
    ]
    reason: str = Field(min_length=1, max_length=5000)
    source_attention_item_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


class FormalAssessmentCreate(BaseModel):
    instrument_name: str = Field(min_length=1, max_length=120)
    instrument_version: str = Field(min_length=1, max_length=80)
    language_locale: str = Field(default="zh-CN", max_length=40)
    score_unit: str = Field(min_length=1, max_length=40)
    administration_mode: str = Field(min_length=1, max_length=40)
    assessed_at: datetime | None = None
    raw_item_results: dict = Field(default_factory=dict)
    subscale_results: dict = Field(default_factory=dict)
    total_result: dict = Field(default_factory=dict)
    metrics: dict[str, float | None] = Field(default_factory=dict)
    missing_items: list = Field(default_factory=list)
    protocol_deviations: dict = Field(default_factory=dict)
    protocol_deviation_reasons: list[str] = Field(default_factory=list)
    notes: str | None = None

