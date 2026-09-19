"""V3 canonical-run storage.  This module deliberately has no V2 consumers."""

from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.algorithm_config import ALGORITHM_CONFIG, R0_CONFIG_VERSION
from app.modules.assessment.model import AssessmentSession
from app.modules.attempts.model import Attempt
from app.modules.evaluation_runs.model import (
    EvaluationAdoptionStatus,
    EvaluationDimensionResult,
    EvaluationReviewRevision,
    EvaluationRun,
    EvaluationSourceType,
)
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate, EvaluationRunCreate, EvaluationRunRead
from app.modules.scenario_dialogues.model import ScenarioDialogueSession
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import PatientProfile, User


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _load_run(db: Session, run_id: UUID, *, lock: bool = False) -> EvaluationRun:
    statement = (
        select(EvaluationRun)
        .where(EvaluationRun.id == run_id)
        .options(selectinload(EvaluationRun.dimension_results), selectinload(EvaluationRun.review_revisions))
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update()
    run = db.scalar(statement)
    if not run:
        raise _not_found("评估运行不存在")
    return run


def source_patient_profile_id(db: Session, source_type: str, source_id: UUID) -> UUID:
    """Resolve polymorphic source ownership before an immutable run is created."""

    if source_type == EvaluationSourceType.attempt.value:
        profile_id = db.scalar(
            select(TrainingSession.patient_profile_id)
            .select_from(Attempt)
            .join(SessionTask, SessionTask.id == Attempt.session_task_id)
            .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
            .where(Attempt.id == source_id)
        )
    elif source_type == EvaluationSourceType.dialogue_session.value:
        profile_id = db.scalar(
            select(TrainingSession.patient_profile_id)
            .select_from(ScenarioDialogueSession)
            .join(TrainingSession, TrainingSession.id == ScenarioDialogueSession.training_session_id)
            .where(ScenarioDialogueSession.id == source_id)
        )
    elif source_type == EvaluationSourceType.assessment_session.value:
        profile_id = db.scalar(select(AssessmentSession.patient_profile_id).where(AssessmentSession.id == source_id))
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未知评估来源类型")
    if not profile_id:
        raise _not_found("评估来源不存在")
    return profile_id


def _canonical_config_snapshot(snapshot: dict) -> dict:
    """Pin the shared R0 config without inventing V3 thresholds in this round."""

    return {
        **deepcopy(snapshot),
        "r0_config_version": R0_CONFIG_VERSION,
    }


def create_candidate_run(db: Session, payload: EvaluationRunCreate) -> EvaluationRun:
    if not db.get(PatientProfile, payload.patient_profile_id):
        raise _not_found("患者档案不存在")
    source_profile_id = source_patient_profile_id(db, payload.source_type, payload.source_id)
    if source_profile_id != payload.patient_profile_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="评估来源不属于该患者档案")

    run = EvaluationRun(
        patient_profile_id=payload.patient_profile_id,
        domain=payload.domain,
        source_type=payload.source_type,
        source_id=payload.source_id,
        algorithm_version=payload.algorithm_version,
        input_fingerprint=payload.input_fingerprint,
        config_snapshot=_canonical_config_snapshot(payload.config_snapshot),
        input_provenance=payload.input_provenance.model_dump(mode="json"),
        quality_gate=payload.quality_gate.model_dump(mode="json"),
        result_status=payload.result_status,
        profile_eligibility=payload.profile_eligibility,
        profile_ineligibility_reasons=payload.profile_ineligibility_reasons,
        limitations=payload.limitations,
        adoption_status=EvaluationAdoptionStatus.candidate.value,
    )
    db.add(run)
    db.flush()
    for item in payload.dimensions:
        db.add(
            EvaluationDimensionResult(
                evaluation_run_id=run.id,
                dimension_code=item.dimension_code,
                value=item.value,
                level=item.level,
                unit=item.unit,
                status=item.status,
                measurement_quality=item.measurement_quality,
                evidence_snapshot=item.evidence_snapshot,
                limitations=item.limitations,
            )
        )
    db.commit()
    return _load_run(db, run.id)


def get_run(db: Session, run_id: UUID) -> EvaluationRun:
    return _load_run(db, run_id)


def list_source_versions(db: Session, source_type: str, source_id: UUID, domain: str) -> list[EvaluationRun]:
    return list(
        db.scalars(
            select(EvaluationRun)
            .where(
                EvaluationRun.source_type == source_type,
                EvaluationRun.source_id == source_id,
                EvaluationRun.domain == domain,
            )
            .order_by(EvaluationRun.created_at.desc())
        )
    )


def get_adopted_run(db: Session, source_type: str, source_id: UUID, domain: str) -> EvaluationRun | None:
    return db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.source_type == source_type,
            EvaluationRun.source_id == source_id,
            EvaluationRun.domain == domain,
            EvaluationRun.adoption_status == EvaluationAdoptionStatus.adopted.value,
        )
    )


def _lock_adoption_scope(db: Session, run: EvaluationRun) -> None:
    """Serialize PostgreSQL adopters before the partial unique index is checked."""

    if db.bind and db.bind.dialect.name == "postgresql":
        key = f"evaluation-adoption:{run.source_type}:{run.source_id}:{run.domain}"
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))


def adopt_candidate_run(db: Session, run_id: UUID) -> EvaluationRun:
    """Atomically replace the adopted run for one source/domain, if any.

    Retrying adoption of the already-adopted same run is intentionally idempotent.
    The partial unique index remains the database-level backstop for concurrent
    transactions, including callers outside this service.
    """

    try:
        with db.begin_nested():
            run = _load_run(db, run_id, lock=True)
            _lock_adoption_scope(db, run)
            if run.adoption_status == EvaluationAdoptionStatus.adopted.value:
                return run
            if run.adoption_status != EvaluationAdoptionStatus.candidate.value:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅候选结果可以采用")
            previous = db.scalar(
                select(EvaluationRun)
                .where(
                    EvaluationRun.source_type == run.source_type,
                    EvaluationRun.source_id == run.source_id,
                    EvaluationRun.domain == run.domain,
                    EvaluationRun.adoption_status == EvaluationAdoptionStatus.adopted.value,
                )
                .with_for_update()
            )
            if previous:
                previous.adoption_status = EvaluationAdoptionStatus.superseded.value
                # Clear the partial unique index before the replacement becomes
                # adopted; ORM batch ordering is otherwise dialect-dependent.
                db.flush()
                run.supersedes_run_id = previous.id
            run.adoption_status = EvaluationAdoptionStatus.adopted.value
            db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Reload the requested run to make retry of the winning run idempotent.
        current = _load_run(db, run_id)
        if current.adoption_status == EvaluationAdoptionStatus.adopted.value:
            return current
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="同一来源已有并发采用的结果") from exc
    return _load_run(db, run_id)


def append_review_revision(db: Session, run_id: UUID, payload: EvaluationReviewRevisionCreate) -> EvaluationReviewRevision:
    run = _load_run(db, run_id)
    if payload.dimension_result_id and not any(item.id == payload.dimension_result_id for item in run.dimension_results):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="复核维度不属于该评估运行")
    if payload.recomputed_run_id and not db.get(EvaluationRun, payload.recomputed_run_id):
        raise _not_found("重算评估运行不存在")
    revision = EvaluationReviewRevision(evaluation_run_id=run.id, **payload.model_dump())
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def get_run_for_professional(db: Session, current_user: User, run_id: UUID) -> EvaluationRunRead:
    run = _load_run(db, run_id)
    profile = db.get(PatientProfile, run.patient_profile_id)
    if not profile:
        raise _not_found("患者档案不存在")
    from app.modules.therapist.service import require_therapist_patient_access

    require_therapist_patient_access(db, current_user, profile.user_id)
    return EvaluationRunRead.model_validate(run)
