from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.evaluation_runs.service import get_run_for_professional
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate
from app.modules.evaluation_runs.functional_communication_v3 import review_or_recompute
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
    run, revision = review_or_recompute(db, current_user, run_id, payload)
    return api_success({"run": get_run_for_professional(db, current_user, run.id).model_dump(mode="json"), "revision_id": str(revision.id) if revision else None})


@router.post("/{run_id}/recompute")
def recompute_evaluation_run(run_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    run, _ = review_or_recompute(db, current_user, run_id)
    return api_success(get_run_for_professional(db, current_user, run.id).model_dump(mode="json"))
