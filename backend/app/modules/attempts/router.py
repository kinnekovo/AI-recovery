from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.attempts import service
from app.modules.attempts.schema import AttemptCreate, AttemptRead
from app.modules.scoring.service import analyze_attempt
from app.modules.users.model import User
from app.modules.users.service import require_patient

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


@router.post("/{attempt_id}/analyze")
def analyze(
    attempt_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    attempt = service.get_attempt(db, current_user, attempt_id)
    score = analyze_attempt(db, attempt)
    return api_success(score.model_dump(mode="json"))
