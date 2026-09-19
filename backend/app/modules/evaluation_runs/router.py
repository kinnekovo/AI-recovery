from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.evaluation_runs.service import get_run_for_professional
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
