from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.model import Attempt
from app.modules.assessment.service import compare_assessments
from app.modules.evaluations.model import (
    AttemptEvaluation,
    EvaluationMetric,
    EvaluationSource,
    ScenarioExpressionReview,
    ScenarioReviewStatus,
)
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.reports.schema import (
    EffectComparisonRead,
    LatestReportRead,
    MetricComparison,
    ProcessMonitoringSummary,
    ScenarioCommunicationSummary,
)
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.training.model import SessionTask, TaskTemplate, TrainingSession, TrainingType
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
    process_summary = build_process_summary(db, profile.id, TrainingType.repeat)
    scenario_summary = build_scenario_communication_summary(db, profile.id)
    effect_comparison = build_effect_comparison(db, user)
    suggestion = build_suggestion(process_summary, scenario_summary, effect_comparison)
    return LatestReportRead(
        training_count=training_count,
        process_monitoring_summary=process_summary,
        scenario_communication_summary=scenario_summary,
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


def build_process_summary(
    db: Session,
    patient_profile_id,
    training_type: TrainingType | None = None,
) -> ProcessMonitoringSummary:
    stmt = (
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
    )
    if training_type:
        stmt = stmt.where(TrainingSession.training_type == training_type)
    rows = db.execute(stmt).all()
    values = {}
    for metric_name, average in rows:
        field_name = PROCESS_AVERAGE_FIELDS.get(metric_name)
        if field_name:
            values[field_name] = round(float(average), 1)
    return ProcessMonitoringSummary(**values)


def build_scenario_communication_summary(db: Session, patient_profile_id) -> ScenarioCommunicationSummary:
    rows = db.execute(
        select(AttemptAnalysisResult.semantic_metrics, ScenarioExpressionReview, Attempt.created_at)
        .join(Attempt, Attempt.id == AttemptAnalysisResult.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TaskTemplate, TaskTemplate.id == SessionTask.task_template_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(ScenarioExpressionReview, ScenarioExpressionReview.attempt_id == Attempt.id)
        .where(
            TrainingSession.patient_profile_id == patient_profile_id,
            TaskTemplate.task_type == TrainingType.scenario,
        )
        .order_by(Attempt.created_at.desc())
    ).all()
    training_scenarios = []
    generalization_probes = []
    reviewed_count = 0
    adjusted_count = 0
    for semantic_metrics, review, created_at in rows:
        details = (semantic_metrics or {}).get("process_monitoring") or {}
        if details.get("evaluation_source") != EvaluationSource.system_rule.value:
            continue
        scenario = details.get("scenario_evaluation")
        if isinstance(scenario, dict):
            scenario = dict(scenario)
            if review and review.review_status in {ScenarioReviewStatus.confirmed, ScenarioReviewStatus.adjusted}:
                reviewed_count += 1
                adjusted_count += int(review.review_status == ScenarioReviewStatus.adjusted)
                if review.goal_status:
                    scenario["goal_status"] = review.goal_status
                overrides = review.information_unit_overrides or {}
                if overrides:
                    units = scenario.get("required_information_units") or []
                    for unit in units:
                        if isinstance(unit, dict) and unit.get("id") in overrides:
                            unit["matched"] = bool(overrides[unit["id"]])
                    matched = sum(1 for unit in units if isinstance(unit, dict) and unit.get("matched"))
                    scenario["information_unit_score"] = round(matched / len(units) * 100, 2) if units else 0.0
                scenario["review_source"] = "therapist"
            (generalization_probes if scenario.get("evaluation_role") == "generalization_probe" else training_scenarios).append(
                (scenario, details, created_at)
            )
    if not training_scenarios and not generalization_probes:
        return ScenarioCommunicationSummary()

    recent = training_scenarios[:5]
    independent_achieved = [
        scenario
        for scenario, details, _created_at in recent
        if scenario.get("goal_status") == "achieved" and float(details.get("independence_score", 0)) >= 90
    ]
    information_scores = [float(scenario.get("information_unit_score", 0)) for scenario, _details, _created_at in recent]
    independence_scores = [float(details.get("independence_score", 0)) for _scenario, details, _created_at in recent]
    if not recent:
        summary = "已完成新场景小测；请先完成日常场景表达，再对照观察泛化。"
    elif len(recent) < 3:
        summary = "已有场景表达记录，样本还少；完成至少 3 次可比场景后再观察趋势。"
    elif independent_achieved:
        summary = "最近场景中已出现独立完成沟通目标的表现；后续应继续观察新场景是否也能做到。"
    else:
        summary = "最近场景仍需要提示或补充关键信息；先把最重要的需求说清楚。"
    probe_recent = generalization_probes[:3]
    probe_independent = [
        scenario
        for scenario, details, _created_at in probe_recent
        if scenario.get("goal_status") == "achieved" and float(details.get("independence_score", 0)) >= 90
    ]
    probe_dates = {created_at.date() for _scenario, _details, created_at in generalization_probes}
    independent_probe_dates = {
        created_at.date()
        for scenario, details, created_at in generalization_probes
        if scenario.get("goal_status") == "achieved" and float(details.get("independence_score", 0)) >= 90
    }
    if not probe_recent:
        generalization_summary = "还没有完成新场景小测，暂时不能判断是否泛化。"
    elif len(probe_dates) < 2:
        generalization_summary = "已有新场景小测，但尚未覆盖两个不同日期；请改天再完成一次，避免用单日表现下结论。"
    elif len(independent_probe_dates) >= 2:
        generalization_summary = "两个不同日期的新场景中都出现独立完成沟通目标的表现，提示可能发生泛化；仍建议治疗师结合录音复核。"
    else:
        generalization_summary = "新场景中仍需要提示或补充信息；这不等同于退步，可据此安排下一轮练习。"
    return ScenarioCommunicationSummary(
        attempt_count=len(training_scenarios),
        recent_valid_count=len(recent),
        independent_goal_achievement_rate=round(len(independent_achieved) / len(recent) * 100, 1) if recent else None,
        median_information_unit_score=round(float(median(information_scores)), 1) if information_scores else None,
        median_independence_score=round(float(median(independence_scores)), 1) if independence_scores else None,
        generalization_probe_count=len(generalization_probes),
        generalization_probe_distinct_date_count=len(probe_dates),
        generalization_independent_goal_achievement_rate=(
            round(len(probe_independent) / len(probe_recent) * 100, 1) if probe_recent else None
        ),
        generalization_summary=generalization_summary,
        therapist_reviewed_count=reviewed_count,
        therapist_adjusted_count=adjusted_count,
        summary=summary,
    )


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


def build_suggestion(
    summary: ProcessMonitoringSummary,
    scenario_summary: ScenarioCommunicationSummary,
    effect: EffectComparisonRead,
) -> str:
    if summary.avg_script_accuracy is None:
        if scenario_summary.attempt_count:
            return scenario_summary.summary
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
