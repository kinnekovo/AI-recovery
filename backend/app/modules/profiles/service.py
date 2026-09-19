from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.algorithm_config import config_value, range_bounds
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentSession
from app.modules.attempts.model import Attempt
from app.modules.evaluations.model import (
    AttemptEvaluation,
    EvaluationMetric,
    EvaluationSource,
    ScenarioExpressionReview,
    ScenarioReviewStatus,
)
from app.modules.evaluations.service import PROCESS_METRIC_NAMES
from app.modules.evaluations.evidence_gate import is_formal_process_evidence
from app.modules.profiles.model import AbilityProfile
from app.modules.profiles.schema import AbilityProfileRead
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.training.model import SessionTask, TrainingSession, TrainingType
from app.modules.users.model import PatientProfile, User, UserRole
from app.modules.users.service import get_patient_profile


RECENT_ATTEMPT_LIMIT = 10


def get_my_ability_profile(db: Session, user: User) -> AbilityProfileRead:
    profile = get_patient_profile(db, user)
    return to_read(refresh_ability_profile(db, profile.id))


def get_patient_ability_profile(db: Session, patient_user_id: UUID) -> AbilityProfileRead:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return to_read(refresh_ability_profile(db, profile.id))


def refresh_ability_profile(db: Session, patient_profile_id: UUID) -> AbilityProfile:
    profile = db.get(PatientProfile, patient_profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")

    process_metrics = recent_process_metrics(db, patient_profile_id)
    reviewed_assessments = reviewed_assessment_summary(db, patient_profile_id)
    reviewed_scenarios = reviewed_scenario_summary(db, patient_profile_id)
    averages = average_metrics(process_metrics)
    content_level, autonomy_level = decide_levels(averages, reviewed_assessments["count"])
    confidence = calculate_confidence(len(process_metrics), reviewed_assessments["count"], reviewed_scenarios["count"])
    summary = build_summary(averages, reviewed_assessments, reviewed_scenarios)
    recommendation = build_recommendation(averages, confidence)

    ability = db.scalar(select(AbilityProfile).where(AbilityProfile.patient_profile_id == patient_profile_id))
    if not ability:
        ability = AbilityProfile(patient_profile_id=patient_profile_id)
        db.add(ability)

    ability.current_content_level = content_level
    ability.current_autonomy_level = autonomy_level
    ability.avg_script_accuracy_recent = averages.get("script_accuracy")
    ability.avg_error_count_recent = averages.get("error_count")
    ability.avg_speech_rate_recent = averages.get("speech_rate")
    ability.avg_loudness_recent = averages.get("loudness")
    ability.assessment_summary = summary
    ability.recommendation = recommendation
    ability.confidence = confidence
    ability.evidence = {
        "recent_attempt_count": len(process_metrics),
        "reviewed_assessment_count": reviewed_assessments["count"],
        "latest_review_status": reviewed_assessments["latest_status"],
        "latest_therapist_notes": reviewed_assessments["latest_notes"],
        "scenario_reviewed_count": reviewed_scenarios["count"],
        "scenario_adjusted_count": reviewed_scenarios["adjusted_count"],
        "scenario_goal_achieved_count": reviewed_scenarios["achieved_count"],
        "latest_scenario_review_notes": reviewed_scenarios["latest_notes"],
        "loudness_unit": "dBFS" if process_metrics else None,
        "algorithm_version": "rehab-process-v2" if process_metrics else None,
        "profile_eligibility": bool(process_metrics),
    }
    db.commit()
    db.refresh(ability)
    return ability


def recent_process_metrics(db: Session, patient_profile_id: UUID) -> list[dict[str, float]]:
    rows = db.execute(
        select(
            Attempt.id,
            Attempt.created_at,
            Attempt.audio_quality,
            AttemptAnalysisResult.semantic_metrics,
            AttemptAnalysisResult.provider_version,
            EvaluationMetric.name,
            AttemptEvaluation.value,
            AttemptEvaluation.unit,
        )
        .join(AttemptEvaluation, AttemptEvaluation.attempt_id == Attempt.id)
        .join(EvaluationMetric, EvaluationMetric.id == AttemptEvaluation.metric_id)
        .join(AttemptAnalysisResult, AttemptAnalysisResult.attempt_id == Attempt.id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(
            TrainingSession.patient_profile_id == patient_profile_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            AttemptEvaluation.decision_eligible.is_(True),
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
            TrainingSession.training_type == TrainingType.repeat,
        )
        .order_by(Attempt.created_at.desc())
    ).all()
    grouped: dict[UUID, dict] = {}
    for attempt_id, created_at, audio_quality, semantic_metrics, provider_version, metric_name, value, unit in rows:
        if attempt_id not in grouped:
            grouped[attempt_id] = {
                "created_at": created_at,
                "audio_quality": audio_quality,
                "semantic_metrics": semantic_metrics or {},
                "provider_version": provider_version,
                "units": {},
                "metrics": {},
            }
        grouped[attempt_id]["metrics"][metric_name] = float(value)
        grouped[attempt_id]["units"][metric_name] = unit
    complete_points = [
        data["metrics"]
        for data in sorted(grouped.values(), key=lambda item: item["created_at"], reverse=True)
        if PROCESS_METRIC_NAMES.issubset(data["metrics"].keys())
        and data["units"].get("loudness") == "dBFS"
        and is_profile_eligible_analysis(data["audio_quality"], data["semantic_metrics"], data["provider_version"])
    ]
    return complete_points[:RECENT_ATTEMPT_LIMIT]


def is_profile_eligible_analysis(
    audio_quality: str | None,
    semantic_metrics: dict | None,
    provider_version: str | None = None,
) -> bool:
    return is_formal_process_evidence(audio_quality, semantic_metrics, provider_version)


def reviewed_assessment_summary(db: Session, patient_profile_id: UUID) -> dict:
    statuses = {AssessmentReviewStatus.confirmed.value, AssessmentReviewStatus.adjusted.value}
    assessments = list(
        db.scalars(
            select(AssessmentSession)
            .where(
                AssessmentSession.patient_profile_id == patient_profile_id,
                AssessmentSession.review_status.in_(statuses),
            )
            .order_by(AssessmentSession.reviewed_at.desc().nullslast(), AssessmentSession.assessed_at.desc())
        )
    )
    latest = assessments[0] if assessments else None
    return {
        "count": len(assessments),
        "latest_status": latest.review_status if latest else None,
        "latest_notes": latest.therapist_notes if latest else None,
    }


def reviewed_scenario_summary(db: Session, patient_profile_id: UUID) -> dict:
    reviews = db.execute(
        select(ScenarioExpressionReview)
        .join(Attempt, Attempt.id == ScenarioExpressionReview.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(
            TrainingSession.patient_profile_id == patient_profile_id,
            TrainingSession.training_type == TrainingType.scenario,
            ScenarioExpressionReview.review_status.in_({ScenarioReviewStatus.confirmed, ScenarioReviewStatus.adjusted}),
        )
        .order_by(ScenarioExpressionReview.reviewed_at.desc().nullslast())
    ).scalars().all()
    latest = reviews[0] if reviews else None
    return {
        "count": len(reviews),
        "adjusted_count": sum(item.review_status == ScenarioReviewStatus.adjusted for item in reviews),
        "achieved_count": sum(item.goal_status == "achieved" for item in reviews),
        "latest_notes": latest.notes if latest else None,
    }


def average_metrics(points: list[dict[str, float]]) -> dict[str, float]:
    if not points:
        return {}
    averages = {}
    for metric_name in PROCESS_METRIC_NAMES:
        values = [point[metric_name] for point in points if metric_name in point]
        if values:
            averages[metric_name] = round(sum(values) / len(values), 1)
    return averages


def decide_levels(averages: dict[str, float], reviewed_count: int) -> tuple[str, str]:
    accuracy = averages.get("script_accuracy")
    errors = averages.get("error_count")
    if accuracy is None or errors is None:
        return "L1", "S1"
    for rule in config_value("profile_level_rules"):
        if accuracy >= rule["accuracy_min"] and errors <= rule["errors_max"] and reviewed_count >= rule["reviewed_min"]:
            return tuple(rule["levels"])
    return "L1", "S1"


def calculate_confidence(attempt_count: int, reviewed_count: int, scenario_review_count: int = 0) -> float:
    weights = config_value("profile_evidence_weights")
    caps = config_value("profile_evidence_caps")
    process_part = min(attempt_count / caps["process"], 1.0) * weights["process"]
    review_part = min(reviewed_count / caps["assessment_review"], 1.0) * weights["assessment_review"]
    scenario_part = min(scenario_review_count / caps["scenario_review"], 1.0) * weights["scenario_review"]
    return round(process_part + review_part + scenario_part, 2)


def build_summary(averages: dict[str, float], reviewed: dict, scenario_reviewed: dict) -> str:
    if not averages and not scenario_reviewed["count"]:
        return "训练数据还不够，完成几次训练后会形成更稳定的能力画像。"
    parts = []
    accuracy = averages.get("script_accuracy")
    errors = averages.get("error_count")
    speech_rate = averages.get("speech_rate")
    loudness = averages.get("loudness")
    if accuracy is not None:
        parts.append("表达完整度较好" if accuracy >= config_value("profile_high_accuracy") else "表达完整度仍需继续练习")
    if errors is not None:
        parts.append("错误较少" if errors <= 1 else "表达中仍有需要留意的错误")
    if speech_rate is not None:
        parts.append("说话节奏偏慢" if speech_rate < config_value("phase43_slow_speech_rate") else "说话节奏较稳定")
    if loudness is not None:
        loudness_min, _ = range_bounds("repeat_loudness_reference")
        parts.append("声音偏轻" if loudness < loudness_min else "声音状态较稳定")
    if reviewed["latest_notes"]:
        parts.append(f"治疗师备注：{reviewed['latest_notes']}")
    if scenario_reviewed["count"]:
        parts.append(
            f"治疗师已复核 {scenario_reviewed['count']} 次场景表达"
            + (f"，其中 {scenario_reviewed['achieved_count']} 次沟通目标已达成" if scenario_reviewed["achieved_count"] else "")
        )
    if scenario_reviewed["latest_notes"]:
        parts.append(f"场景复核备注：{scenario_reviewed['latest_notes']}")
    return "；".join(parts) + "。"


def build_recommendation(averages: dict[str, float], confidence: float) -> str:
    if not averages:
        return "先完成几次基础训练，系统会逐步给出更贴合的建议。"
    gate = config_value("profile_recommendation_gate")
    if confidence < gate["confidence_min"]:
        return "当前画像置信度还不高，建议继续保持每日训练并等待治疗师复核。"
    if averages.get("script_accuracy", 100) < gate["accuracy_low"] or averages.get("error_count", 0) >= gate["errors_high"]:
        return "建议先使用短句和高提示训练，把一句话说完整后再提高难度。"
    if averages.get("speech_rate", 200) < config_value("phase43_slow_speech_rate"):
        return "建议增加熟悉短句的连续表达练习，重点减少停顿。"
    loudness_min, _ = range_bounds("repeat_loudness_reference")
    if averages.get("loudness", -24) < loudness_min:
        return "建议增加声音稳定练习，先坐直、慢吸气，再把句子清楚说完。"
    return "可以继续当前训练节奏，下一步逐步增加句子长度和自主表达比例。"


def to_read(ability: AbilityProfile) -> AbilityProfileRead:
    return AbilityProfileRead.model_validate(ability)
