from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assessment.model import AssessmentSession, AssessmentType
from app.modules.assessment.schema import (
    AssessmentCompareRead,
    AssessmentCreate,
    AssessmentRead,
    LONG_TERM_METRIC_NAMES,
    PROCESS_METRIC_NAMES,
    MetricComparison,
)
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile
from app.database.base import utc_now


def create_assessment(db: Session, user: User, payload: AssessmentCreate) -> AssessmentRead:
    profile = get_patient_profile(db, user)
    assessment = AssessmentSession(
        patient_profile_id=profile.id,
        assessment_type=payload.assessment_type,
        evaluation_source=payload.evaluation_source,
        assessed_at=payload.assessed_at or utc_now(),
        metrics=payload.metrics.compact(),
        notes=payload.notes,
        instrument_name=payload.instrument_name, instrument_version=payload.instrument_version,
        language_locale=payload.language_locale, localization_version=payload.localization_version,
        assessment_stage=payload.assessment_stage, raw_item_results=payload.raw_item_results,
        subscale_results=payload.subscale_results, total_result=payload.total_result,
        missing_items=payload.missing_items, score_unit=payload.score_unit,
        administration_mode=payload.administration_mode, device_and_environment=payload.device_and_environment,
        duration_seconds=payload.duration_seconds, protocol_deviations=payload.protocol_deviations,
        protocol_deviation_reasons=payload.protocol_deviation_reasons,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return to_read(assessment)


def list_history(
    db: Session,
    user: User,
    assessment_type: AssessmentType | None = None,
) -> list[AssessmentRead]:
    profile = get_patient_profile(db, user)
    stmt = (
        select(AssessmentSession)
        .where(AssessmentSession.patient_profile_id == profile.id)
        .order_by(AssessmentSession.assessed_at.asc(), AssessmentSession.created_at.asc())
    )
    if assessment_type:
        stmt = stmt.where(AssessmentSession.assessment_type == assessment_type)
    return [to_read(item) for item in db.scalars(stmt)]


def compare_assessments(
    db: Session,
    user: User,
    baseline_id: UUID | None = None,
    current_id: UUID | None = None,
) -> AssessmentCompareRead:
    history = list_history_raw(db, user)
    if not history:
        return AssessmentCompareRead(baseline_assessment=None, current_assessment=None, metrics={})

    baseline = get_owned_assessment(db, user, baseline_id) if baseline_id else history[0]
    current = get_owned_assessment(db, user, current_id) if current_id else history[-1]
    metric_names = sorted(LONG_TERM_METRIC_NAMES | PROCESS_METRIC_NAMES | set(baseline.metrics.keys()) | set(current.metrics.keys()))
    comparisons = {
        name: MetricComparison(
            baseline=baseline.metrics.get(name),
            current=current.metrics.get(name),
            change=calculate_change(baseline.metrics.get(name), current.metrics.get(name)),
        )
        for name in metric_names
    }
    return AssessmentCompareRead(
        baseline_assessment=to_read(baseline),
        current_assessment=to_read(current),
        metrics=comparisons,
    )


def list_history_raw(db: Session, user: User) -> list[AssessmentSession]:
    profile = get_patient_profile(db, user)
    return list(
        db.scalars(
            select(AssessmentSession)
            .where(AssessmentSession.patient_profile_id == profile.id)
            .order_by(AssessmentSession.assessed_at.asc(), AssessmentSession.created_at.asc())
        )
    )


def get_owned_assessment(db: Session, user: User, assessment_id: UUID) -> AssessmentSession:
    profile = get_patient_profile(db, user)
    assessment = db.get(AssessmentSession, assessment_id)
    if not assessment or assessment.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶段性评估不存在")
    return assessment


def calculate_change(baseline: float | None, current: float | None) -> float | None:
    if baseline is None or current is None:
        return None
    return round(float(current) - float(baseline), 2)


def to_read(assessment: AssessmentSession) -> AssessmentRead:
    return AssessmentRead(
        id=assessment.id,
        patient_profile_id=assessment.patient_profile_id,
        source_attempt_id=assessment.source_attempt_id,
        assessment_type=assessment.assessment_type,
        evaluation_source=assessment.evaluation_source,
        review_status=assessment.review_status,
        reviewed_by_user_id=assessment.reviewed_by_user_id,
        reviewed_at=assessment.reviewed_at,
        assessed_at=assessment.assessed_at,
        metrics=assessment.metrics,
        notes=assessment.notes,
        therapist_notes=assessment.therapist_notes,
        created_at=assessment.created_at,
        instrument_name=assessment.instrument_name, instrument_version=assessment.instrument_version,
        language_locale=assessment.language_locale, localization_version=assessment.localization_version,
        assessment_stage=assessment.assessment_stage, raw_item_results=assessment.raw_item_results,
        subscale_results=assessment.subscale_results, total_result=assessment.total_result,
        missing_items=assessment.missing_items, score_unit=assessment.score_unit,
        administration_mode=assessment.administration_mode,
    )
