from pydantic import BaseModel, Field


class ProcessMonitoringSummary(BaseModel):
    avg_script_accuracy: float | None = None
    avg_error_count: float | None = None
    avg_speech_rate: float | None = None
    avg_loudness: float | None = None


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
    effect_comparison: EffectComparisonRead
    suggestion: str
