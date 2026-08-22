from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.attempts.model import Attempt
from app.modules.files.model import FileAsset, FileType
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import FamilyPatientBinding, PatientProfile, User, UserRole


FILE_TYPE_DIRS = {
    FileType.agent_image: "agent-images",
    FileType.voice_sample: "voice-samples",
    FileType.training_audio: "training-audio",
    FileType.generated_audio: "generated-audio",
}


def storage_dir(file_type: FileType) -> Path:
    root = get_settings().storage_root
    path = root / FILE_TYPE_DIRS[file_type]
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_url(asset: FileAsset) -> str:
    return f"/api/files/{asset.id}/content"


def save_upload(db: Session, user: User, upload: UploadFile, file_type: FileType) -> FileAsset:
    suffix = Path(upload.filename or "upload.bin").suffix
    filename = f"{uuid4()}{suffix}"
    destination = storage_dir(file_type) / filename
    content = upload.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    destination.write_bytes(content)
    asset = FileAsset(
        owner_user_id=user.id,
        file_type=file_type,
        original_name=upload.filename or filename,
        storage_path=str(destination),
        mime_type=upload.content_type,
        size_bytes=len(content),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_accessible_file(db: Session, user: User, file_id) -> FileAsset:
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if asset.owner_user_id == user.id:
        return asset
    if asset.file_type == FileType.training_audio and can_access_training_audio(db, user, asset):
        return asset
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")


def can_access_training_audio(db: Session, user: User, asset: FileAsset) -> bool:
    if user.role in {UserRole.therapist, UserRole.admin}:
        return bool(db.scalar(select(Attempt.id).where(Attempt.audio_file_id == asset.id).limit(1)))
    if user.role != UserRole.family:
        return False
    return bool(
        db.scalar(
            select(Attempt.id)
            .join(SessionTask, SessionTask.id == Attempt.session_task_id)
            .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
            .join(PatientProfile, PatientProfile.id == TrainingSession.patient_profile_id)
            .join(FamilyPatientBinding, FamilyPatientBinding.patient_profile_id == PatientProfile.id)
            .where(
                Attempt.audio_file_id == asset.id,
                FamilyPatientBinding.family_user_id == user.id,
                FamilyPatientBinding.status == "active",
            )
            .limit(1)
        )
    )
