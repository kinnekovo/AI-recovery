from pydantic import BaseModel, Field


class ProcessMonitoringSummary(BaseModel):
    avg_script_accuracy: float | None = None
    avg_error_count: float | None = None
    avg_speech_rate: float | None = None
    avg_loudness: float | None = None


class ScenarioCommunicationSummary(BaseModel):
    attempt_count: int = 0
    recent_valid_count: int = 0
    independent_goal_achievement_rate: float | None = None
    median_information_unit_score: float | None = None
    median_independence_score: float | None = None
    generalization_probe_count: int = 0
    generalization_probe_distinct_date_count: int = 0
    generalization_independent_goal_achievement_rate: float | None = None
    generalization_summary: str = "尚未完成新场景泛化探测。"
    therapist_reviewed_count: int = 0
    therapist_adjusted_count: int = 0
    summary: str = "还没有完成可用的场景表达反馈。"


class MetricComparison(BaseModel):
    baseline: float | None = None
    current: float | None = None
    change: float | None = None


class EffectComparisonRead(BaseModel):
    has_comparison: bool = False
    wab: dict[str, MetricComparison] = Field(default_factory=dict)
    cadl: MetricComparison | None = None
    acceptance: MetricComparison | None = None


class LatestReportRead(BaseModel):
    training_count: int
    process_monitoring_summary: ProcessMonitoringSummary
    scenario_communication_summary: ScenarioCommunicationSummary
    effect_comparison: EffectComparisonRead
    suggestion: str
