from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.model import Attempt
from app.modules.assessment.service import compare_assessments
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.reports.schema import EffectComparisonRead, LatestReportRead, MetricComparison, ProcessMonitoringSummary
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile


PROCESS_AVERAGE_FIELDS = {
    "script_accuracy": "avg_script_accuracy",
    "error_count": "avg_error_count",
    "speech_rate": "avg_speech_rate",
    "loudness": "avg_loudness",
}

WAB_METRIC_NAMES = {
    "wab_information",
    "wab_fluency",
    "wab_grammar",
    "wab_word_order",
    "wab_comprehensibility",
    "wab_repetition_comprehensibility",
}


def latest_report(db: Session, user: User) -> LatestReportRead:
    profile = get_patient_profile(db, user)
    training_count = count_evaluated_attempts(db, profile.id)
    process_summary = build_process_summary(db, profile.id)
    effect_comparison = build_effect_comparison(db, user)
    suggestion = build_suggestion(process_summary, effect_comparison)
    return LatestReportRead(
        training_count=training_count,
        process_monitoring_summary=process_summary,
        effect_comparison=effect_comparison,
        suggestion=suggestion,
    )


def count_evaluated_attempts(db: Session, patient_profile_id) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(Attempt.id)))
            .join(AttemptEvaluation, AttemptEvaluation.attempt_id == Attempt.id)
            .join(EvaluationMetric, EvaluationMetric.id == AttemptEvaluation.metric_id)
            .join(SessionTask, SessionTask.id == Attempt.session_task_id)
            .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
            .where(
                TrainingSession.patient_profile_id == patient_profile_id,
                AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
                EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
            )
        )
        or 0
    )


def build_process_summary(db: Session, patient_profile_id) -> ProcessMonitoringSummary:
    rows = db.execute(
        select(EvaluationMetric.name, func.avg(AttemptEvaluation.value))
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .join(Attempt, Attempt.id == AttemptEvaluation.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(
            TrainingSession.patient_profile_id == patient_profile_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
        .group_by(EvaluationMetric.name)
    ).all()
    values = {}
    for metric_name, average in rows:
        field_name = PROCESS_AVERAGE_FIELDS.get(metric_name)
        if field_name:
            values[field_name] = round(float(average), 1)
    return ProcessMonitoringSummary(**values)


def build_effect_comparison(db: Session, user: User) -> EffectComparisonRead:
    comparison = compare_assessments(db, user)
    has_comparison = bool(
        comparison.baseline_assessment
        and comparison.current_assessment
        and comparison.baseline_assessment.id != comparison.current_assessment.id
    )
    wab = {
        name: MetricComparison(**item.model_dump())
        for name, item in comparison.metrics.items()
        if name in WAB_METRIC_NAMES
    }
    cadl_source = comparison.metrics.get("cadl_score")
    acceptance_source = comparison.metrics.get("acceptance_score")
    return EffectComparisonRead(
        has_comparison=has_comparison,
        wab=wab,
        cadl=MetricComparison(**cadl_source.model_dump()) if cadl_source else None,
        acceptance=MetricComparison(**acceptance_source.model_dump()) if acceptance_source else None,
    )


def build_suggestion(summary: ProcessMonitoringSummary, effect: EffectComparisonRead) -> str:
    if summary.avg_script_accuracy is None:
        return "完成一次训练后，系统会给出下一步练习建议。"
    if summary.avg_script_accuracy < 70 or (summary.avg_error_count is not None and summary.avg_error_count >= 4):
        return "建议先练短句，把一句话说完整，再慢慢增加难度。"
    if summary.avg_speech_rate is not None and summary.avg_speech_rate < 180:
        return "可以继续练熟悉短句，重点放在少停顿、连起来说。"
    if summary.avg_loudness is not None and summary.avg_loudness < -35:
        return "可以试着把声音放清楚一点，不用着急，稳定开口最重要。"
    if effect.has_comparison:
        return "最近练习比较稳定，可以继续保持今天的训练节奏。"
    return "最近练习比较稳定，继续完成日常训练就很好。"
