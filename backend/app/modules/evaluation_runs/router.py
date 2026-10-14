from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.evaluation_runs.service import get_run_for_professional
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate
from app.modules.evaluation_runs import functional_communication_v3, repeat_v3
from app.modules.evaluation_runs.service import get_run
from app.modules.users.model import User
from app.modules.users.service import require_therapist


router = APIRouter(prefix="/evaluation-runs", tags=["evaluation-runs"])


@router.get("/{run_id}")
def get_evaluation_run(
    run_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    """Professional-only canonical V3 read; V3 is not patient-facing this round."""

    return api_success(get_run_for_professional(db, current_user, run_id).model_dump(mode="json"))


@router.post("/{run_id}/reviews")
def review_evaluation_run(run_id: UUID, payload: EvaluationReviewRevisionCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    current = get_run(db, run_id)
    handler = {"repeat": repeat_v3.review_or_recompute, "functional_communication": functional_communication_v3.review_or_recompute}.get(current.domain)
    if not handler:
        raise HTTPException(status_code=409, detail="该类型暂不支持人工复核")
    run, revision = handler(db, current_user, run_id, payload)
    return api_success({"run": get_run_for_professional(db, current_user, run.id).model_dump(mode="json"), "revision_id": str(revision.id) if revision else None})


@router.post("/{run_id}/recompute")
def recompute_evaluation_run(run_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    current = get_run(db, run_id)
    handler = {"repeat": repeat_v3.review_or_recompute, "functional_communication": functional_communication_v3.review_or_recompute}.get(current.domain)
    if not handler:
        raise HTTPException(status_code=409, detail="该类型暂不支持重新计算")
    run, _ = handler(db, current_user, run_id)
    return api_success(get_run_for_professional(db, current_user, run.id).model_dump(mode="json"))
