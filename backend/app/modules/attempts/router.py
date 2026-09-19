from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.attempts import service
from app.modules.attempts.schema import AttemptCreate, AttemptRead
from app.modules.scoring.service import analyze_attempt
from app.modules.pronunciation.service import get_patient_attempt_pronunciation
from app.modules.evaluation_runs.repeat_v3 import get_adopted_repeat_run, require_repeat_professional_access
from app.modules.evaluation_runs.service import get_run_for_professional
from app.modules.users.model import User
from app.modules.users.service import require_patient, require_therapist

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("")
def create_attempt(
    payload: AttemptCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    attempt = service.create_attempt(db, current_user, payload)
    return api_success(AttemptRead.model_validate(attempt).model_dump(mode="json"))


@router.post("/{attempt_id}/audio")
def upload_audio(
    attempt_id: UUID,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    attempt = service.upload_audio(db, current_user, attempt_id, audio_file)
    return api_success(AttemptRead.model_validate(attempt).model_dump(mode="json"))


@router.get("/{attempt_id}")
def get_attempt(
    attempt_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    attempt = service.get_attempt(db, current_user, attempt_id)
    return api_success(AttemptRead.model_validate(attempt).model_dump(mode="json"))


@router.get("/{attempt_id}/pronunciation")
def pronunciation(
    attempt_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    service.get_attempt(db, current_user, attempt_id)
    result = get_patient_attempt_pronunciation(db, attempt_id)
    return api_success(result.model_dump(mode="json"))


@router.post("/{attempt_id}/analyze")
def analyze(
    attempt_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    attempt = service.get_attempt(db, current_user, attempt_id)
    score = analyze_attempt(db, attempt)
    return api_success(score.model_dump(mode="json"))


@router.get("/{attempt_id}/evaluation-v3")
def evaluation_v3(
    attempt_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    require_repeat_professional_access(db, current_user, attempt_id)
    run = get_adopted_repeat_run(db, attempt_id)
    if not run:
        return api_success({"status": "not_generated", "attempt_id": str(attempt_id)})
    return api_success(get_run_for_professional(db, current_user, run.id).model_dump(mode="json"))
