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
from app.modules.therapist.schema import TherapistPatientRead
from app.modules.training.model import SessionTask, TrainingSession
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
