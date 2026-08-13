from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentSession, AssessmentType
from app.modules.assessment.schema import (
    AssessmentCompareRead,
    AssessmentCreate,
    AssessmentRead,
    AssessmentReviewUpdate,
    LONG_TERM_METRIC_NAMES,
    PROCESS_METRIC_NAMES,
    MetricComparison,
)
from app.modules.assessment.service import calculate_change, to_read
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.scoring.model import AttemptScore
from app.modules.therapist.schema import (
    RecommendationNoteRead,
    TherapistPatientRead,
    TherapistTrainingRecordRead,
    TherapistTrainingTrendsRead,
    TherapistTrendBucketRead,
)
from app.modules.training.model import (
    RecommendationStrategyFeedback,
    SessionTask,
    StrategyFeedbackJudgment,
    TrainingSession,
)
from app.modules.users.model import PatientProfile, User, UserRole


def list_patients(db: Session) -> list[TherapistPatientRead]:
    backfill_auto_assessments(db)
    rows = db.execute(
        select(
            User,
            PatientProfile,
            func.count(AssessmentSession.id).filter(
                AssessmentSession.review_status == AssessmentReviewStatus.pending_review.value
            ),
            func.max(AssessmentSession.assessed_at),
        )
        .join(PatientProfile, PatientProfile.user_id == User.id)
        .outerjoin(AssessmentSession, AssessmentSession.patient_profile_id == PatientProfile.id)
        .where(User.role == UserRole.patient)
        .group_by(User.id, PatientProfile.id)
        .order_by(User.created_at.desc())
    ).all()
    return [
        TherapistPatientRead(
            user_id=user.id,
            patient_profile_id=profile.id,
            username=user.username,
            assessment_status=profile.assessment_status,
            training_status=profile.training_status,
            pending_review_count=pending_review_count,
            latest_assessment_at=latest_assessment_at,
            created_at=user.created_at,
        )
        for user, profile, pending_review_count, latest_assessment_at in rows
    ]


def backfill_auto_assessments(db: Session) -> None:
    profiles = list(db.scalars(select(PatientProfile)))
    changed = False
    for profile in profiles:
        changed = backfill_profile_auto_assessments(db, profile) or changed
    if changed:
        db.commit()


def backfill_profile_auto_assessments(db: Session, profile: PatientProfile) -> bool:
    changed = False
    attempts = db.execute(
        select(Attempt)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(AssessmentSession, AssessmentSession.source_attempt_id == Attempt.id)
        .where(
            TrainingSession.patient_profile_id == profile.id,
            Attempt.analysis_status == AnalysisStatus.completed,
            AssessmentSession.id.is_(None),
        )
        .order_by(Attempt.created_at.asc())
    ).scalars()
    for attempt in attempts:
        metrics = process_metrics_for_attempt(db, attempt.id)
        if PROCESS_METRIC_NAMES.issubset(metrics.keys()):
            db.add(
                AssessmentSession(
                    patient_profile_id=profile.id,
                    source_attempt_id=attempt.id,
                    assessment_type=AssessmentType.during,
                    evaluation_source=EvaluationSource.mock_ai,
                    review_status=AssessmentReviewStatus.pending_review.value,
                    assessed_at=attempt.created_at,
                    metrics=metrics,
                    notes="系统根据历史训练分析自动补生成，等待治疗师复核。",
                )
            )
            profile.assessment_status = "started"
            changed = True
    return changed


def process_metrics_for_attempt(db: Session, attempt_id: UUID) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .where(
            AttemptEvaluation.attempt_id == attempt_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
            EvaluationMetric.name.in_(PROCESS_METRIC_NAMES),
        )
    ).all()
    return {name: float(value) for name, value in rows}


def list_patient_training_records(
    db: Session,
    patient_user_id: UUID,
    limit: int = 30,
) -> list[TherapistTrainingRecordRead]:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    rows = db.execute(
        select(Attempt, TrainingSession, SessionTask, AttemptScore)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(AttemptScore, AttemptScore.attempt_id == Attempt.id)
        .where(TrainingSession.patient_profile_id == profile.id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    ).all()
    return [
        TherapistTrainingRecordRead(
            attempt_id=attempt.id,
            session_id=session.id,
            created_at=attempt.created_at,
            training_type=session.training_type,
            task_title=task.task_template.title,
            target_text=task.task_template.target_text,
            analysis_status=attempt.analysis_status.value,
            overall_score=score.overall_score if score else None,
            content_score=score.content_score if score else None,
            clarity_score=score.clarity_score if score else None,
            fluency_score=score.fluency_score if score else None,
            loudness_score=score.loudness_score if score else None,
            process_metrics=process_metrics_for_attempt(db, attempt.id),
            feedback_summary=score.suggestion if score else attempt_status_summary(attempt),
            recommendation_source=session.recommendation_source,
            recommendation_matched=session.recommendation_matched,
        )
        for attempt, session, task, score in rows
    ]


def get_patient_training_trends(db: Session, patient_user_id: UUID) -> TherapistTrainingTrendsRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    now = utc_now()
    rows = db.execute(
        select(Attempt, AttemptScore)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .outerjoin(AttemptScore, AttemptScore.attempt_id == Attempt.id)
        .where(TrainingSession.patient_profile_id == profile.id)
        .order_by(Attempt.created_at.desc())
    ).all()
    buckets = [
        build_trend_bucket(db, "latest", "上次", rows[:1]),
        build_trend_bucket(db, "days_3", "三天内", filter_attempt_rows(rows, now - timedelta(days=3))),
        build_trend_bucket(db, "days_7", "七天内", filter_attempt_rows(rows, now - timedelta(days=7))),
        build_trend_bucket(db, "days_30", "三十天内", filter_attempt_rows(rows, now - timedelta(days=30))),
    ]
    latest = buckets[0]
    month = buckets[-1]
    if latest.attempt_count == 0:
        summary = "还没有训练评分，完成一次训练后这里会显示趋势。"
    elif month.attempt_count <= 1:
        summary = "已有最近一次训练结果，样本还少，建议继续观察。"
    elif latest.avg_overall_score is not None and month.avg_overall_score is not None:
        delta = round(latest.avg_overall_score - month.avg_overall_score, 1)
        if delta >= 3:
            summary = "最近一次整体分数高于三十天均值，训练方向暂时有效。"
        elif delta <= -3:
            summary = "最近一次整体分数低于三十天均值，需要关注难度或状态波动。"
        else:
            summary = "最近一次整体表现接近三十天均值，状态相对稳定。"
    else:
        summary = "已汇总近期过程指标，评分样本仍在积累。"
    return TherapistTrainingTrendsRead(buckets=buckets, overall_summary=summary)


def save_recommendation_note(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    note: str | None,
) -> RecommendationNoteRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    cleaned_note = (note or "").strip() or None
    feedback = RecommendationStrategyFeedback(
        patient_profile_id=profile.id,
        therapist_user_id=therapist.id,
        trend_status="manual_note",
        judgment=StrategyFeedbackJudgment.observe,
        reason="治疗师自然语言调整推荐训练内容。",
        next_strategy=cleaned_note,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return RecommendationNoteRead(note=feedback.next_strategy, updated_at=feedback.created_at)


def get_latest_recommendation_note(db: Session, patient_user_id: UUID) -> RecommendationNoteRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    feedback = db.scalar(
        select(RecommendationStrategyFeedback)
        .where(
            RecommendationStrategyFeedback.patient_profile_id == profile.id,
            RecommendationStrategyFeedback.trend_status == "manual_note",
        )
        .order_by(RecommendationStrategyFeedback.created_at.desc())
    )
    return RecommendationNoteRead(
        note=feedback.next_strategy if feedback else None,
        updated_at=feedback.created_at if feedback else None,
    )


def filter_attempt_rows(rows, since):
    return [(attempt, score) for attempt, score in rows if attempt.created_at >= since]


def build_trend_bucket(db: Session, key: str, label: str, rows) -> TherapistTrendBucketRead:
    metrics_list = [process_metrics_for_attempt(db, attempt.id) for attempt, _score in rows]
    scores = [float(score.overall_score) for _attempt, score in rows if score]
    metrics = {
        "script_accuracy": average_metric(metrics_list, "script_accuracy"),
        "error_count": average_metric(metrics_list, "error_count"),
        "speech_rate": average_metric(metrics_list, "speech_rate"),
        "loudness": average_metric(metrics_list, "loudness"),
    }
    attempt_count = len(rows)
    return TherapistTrendBucketRead(
        key=key,
        label=label,
        attempt_count=attempt_count,
        avg_overall_score=round(sum(scores) / len(scores), 1) if scores else None,
        avg_script_accuracy=metrics["script_accuracy"],
        avg_error_count=metrics["error_count"],
        avg_speech_rate=metrics["speech_rate"],
        avg_loudness=metrics["loudness"],
        summary=trend_bucket_summary(attempt_count, metrics),
    )


def average_metric(metrics_list: list[dict[str, float]], name: str) -> float | None:
    values = [metrics[name] for metrics in metrics_list if name in metrics]
    return round(sum(values) / len(values), 1) if values else None


def trend_bucket_summary(attempt_count: int, metrics: dict[str, float | None]) -> str:
    if attempt_count == 0:
        return "暂无训练。"
    parts = []
    accuracy = metrics.get("script_accuracy")
    errors = metrics.get("error_count")
    speech_rate = metrics.get("speech_rate")
    loudness = metrics.get("loudness")
    if accuracy is not None:
        parts.append("表达完整度较好" if accuracy >= 90 else "表达完整度需关注")
    if errors is not None:
        parts.append("错误较少" if errors <= 1 else "错误偏多")
    if speech_rate is not None:
        parts.append("节奏稳定" if 180 <= speech_rate <= 240 else "节奏需观察")
    if loudness is not None:
        parts.append("音量稳定" if 60 <= loudness <= 78 else "音量需观察")
    return "，".join(parts) + "。" if parts else "已有训练记录，暂缺完整指标。"


def attempt_status_summary(attempt: Attempt) -> str:
    if attempt.analysis_status == AnalysisStatus.pending:
        return "录音已提交，系统正在分析评分。"
    if attempt.analysis_status == AnalysisStatus.failed:
        return "本次录音分析失败，可让患者重新完成一次。"
    return "系统已完成过程分析，暂无总评分。"


def create_patient_assessment(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    payload: AssessmentCreate,
) -> AssessmentRead:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    assessment = AssessmentSession(
        patient_profile_id=profile.id,
        assessment_type=payload.assessment_type,
        evaluation_source=payload.evaluation_source,
        review_status=AssessmentReviewStatus.confirmed.value,
        reviewed_by_user_id=therapist.id,
        reviewed_at=utc_now(),
        assessed_at=payload.assessed_at or utc_now(),
        metrics=payload.metrics.compact(),
        notes=payload.notes,
        therapist_notes="治疗师补录评估。",
    )
    db.add(assessment)
    profile.assessment_status = "started"
    db.commit()
    db.refresh(assessment)
    from app.modules.profiles.service import refresh_ability_profile

    refresh_ability_profile(db, profile.id)
    db.refresh(assessment)
    return to_read(assessment)


def list_patient_assessments(
    db: Session,
    patient_user_id: UUID,
    assessment_type: AssessmentType | None = None,
    review_status: AssessmentReviewStatus | None = None,
) -> list[AssessmentRead]:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    if backfill_profile_auto_assessments(db, profile):
        db.commit()
    stmt = (
        select(AssessmentSession)
        .where(AssessmentSession.patient_profile_id == profile.id)
        .order_by(AssessmentSession.assessed_at.asc(), AssessmentSession.created_at.asc())
    )
    if assessment_type:
        stmt = stmt.where(AssessmentSession.assessment_type == assessment_type)
    if review_status:
        stmt = stmt.where(AssessmentSession.review_status == review_status.value)
    return [to_read(item) for item in db.scalars(stmt)]


def review_patient_assessment(
    db: Session,
    therapist: User,
    patient_user_id: UUID,
    assessment_id: UUID,
    payload: AssessmentReviewUpdate,
) -> AssessmentRead:
    assessment = get_owned_assessment(db, patient_user_id, assessment_id)
    if payload.metrics is not None:
        assessment.metrics = {**assessment.metrics, **payload.metrics}
    if payload.notes is not None:
        assessment.notes = payload.notes
    assessment.therapist_notes = payload.therapist_notes
    assessment.review_status = payload.review_status.value
    assessment.reviewed_by_user_id = therapist.id
    assessment.reviewed_at = utc_now()
    db.commit()
    db.refresh(assessment)
    from app.modules.profiles.service import refresh_ability_profile

    refresh_ability_profile(db, assessment.patient_profile_id)
    db.refresh(assessment)
    return to_read(assessment)


def compare_patient_assessments(
    db: Session,
    patient_user_id: UUID,
    baseline_id: UUID | None = None,
    current_id: UUID | None = None,
) -> AssessmentCompareRead:
    history = list_patient_assessments_raw(db, patient_user_id)
    if not history:
        return AssessmentCompareRead(baseline_assessment=None, current_assessment=None, metrics={})
    baseline = get_owned_assessment(db, patient_user_id, baseline_id) if baseline_id else history[0]
    current = get_owned_assessment(db, patient_user_id, current_id) if current_id else history[-1]
    metric_names = sorted(LONG_TERM_METRIC_NAMES | PROCESS_METRIC_NAMES | set(baseline.metrics.keys()) | set(current.metrics.keys()))
    return AssessmentCompareRead(
        baseline_assessment=to_read(baseline),
        current_assessment=to_read(current),
        metrics={
            name: MetricComparison(
                baseline=baseline.metrics.get(name),
                current=current.metrics.get(name),
                change=calculate_change(baseline.metrics.get(name), current.metrics.get(name)),
            )
            for name in metric_names
        },
    )


def list_patient_assessments_raw(db: Session, patient_user_id: UUID) -> list[AssessmentSession]:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    return list(
        db.scalars(
            select(AssessmentSession)
            .where(AssessmentSession.patient_profile_id == profile.id)
            .order_by(AssessmentSession.assessed_at.asc(), AssessmentSession.created_at.asc())
        )
    )


def get_owned_assessment(db: Session, patient_user_id: UUID, assessment_id: UUID) -> AssessmentSession:
    profile = get_patient_profile_by_user_id(db, patient_user_id)
    assessment = db.get(AssessmentSession, assessment_id)
    if not assessment or assessment.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段性评估不存在")
    return assessment


def get_patient_profile_by_user_id(db: Session, patient_user_id: UUID) -> PatientProfile:
    patient = db.get(User, patient_user_id)
    if not patient or patient.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return profile
