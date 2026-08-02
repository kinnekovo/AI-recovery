from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.model import Attempt
from app.modules.attempts.schema import AttemptCreate
from app.modules.files.model import FileType
from app.modules.files.service import save_upload
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile


def _get_owned_session_task(db: Session, user: User, session_task_id: UUID) -> SessionTask:
    profile = get_patient_profile(db, user)
    task = db.get(SessionTask, session_task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练任务不存在")
    session = db.get(TrainingSession, task.training_session_id)
    if not session or session.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练任务不存在")
    return task


def create_attempt(db: Session, user: User, payload: AttemptCreate) -> Attempt:
    _get_owned_session_task(db, user, payload.session_task_id)
    count = db.scalar(select(func.count(Attempt.id)).where(Attempt.session_task_id == payload.session_task_id)) or 0
    attempt = Attempt(
        session_task_id=payload.session_task_id,
        attempt_no=count + 1,
        prompt_level=payload.prompt_level,
        start_latency_ms=payload.start_latency_ms,
        duration_ms=payload.duration_ms,
        skipped=payload.skipped,
        requested_help=payload.requested_help,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_attempt(db: Session, user: User, attempt_id: UUID) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作答不存在")
    _get_owned_session_task(db, user, attempt.session_task_id)
    return attempt


def upload_audio(db: Session, user: User, attempt_id: UUID, upload: UploadFile) -> Attempt:
    attempt = get_attempt(db, user, attempt_id)
    asset = save_upload(db, user, upload, FileType.training_audio)
    attempt.audio_file_id = asset.id
    attempt.audio_quality = "mock_pass"
    db.commit()
    db.refresh(attempt)
    return attempt
