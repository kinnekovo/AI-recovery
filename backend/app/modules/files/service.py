from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.observability import log_event
from app.modules.attempts.model import Attempt
from app.modules.files.model import FileAsset, FileStatus, FileType
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import FamilyPatientBinding, PatientProfile, TherapistPatientAssignment, User, UserRole


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
        log_event("warning", "file", "empty_upload", user_id=str(user.id), file_type=file_type.value)
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
    if not asset or asset.status != FileStatus.active:
        log_event("warning", "file", "file_not_found", user_id=str(user.id), file_id=str(file_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if asset.owner_user_id == user.id:
        return asset
    if user.role == UserRole.admin:
        return asset
    if asset.file_type == FileType.agent_image and can_access_agent_image(db, user, asset):
        return asset
    if asset.file_type == FileType.training_audio and can_access_training_audio(db, user, asset):
        return asset
    log_event(
        "warning",
        "file",
        "file_access_denied",
        user_id=str(user.id),
        user_role=user.role.value,
        file_id=str(asset.id),
        file_type=asset.file_type.value,
        owner_user_id=str(asset.owner_user_id),
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")


def can_access_agent_image(db: Session, user: User, asset: FileAsset) -> bool:
    from app.modules.agents.model import Agent

    profile_id = db.scalar(select(Agent.patient_profile_id).where(Agent.avatar_file_id == asset.id).limit(1))
    return bool(profile_id and can_access_patient_profile_file(db, user, profile_id))


def can_access_training_audio(db: Session, user: User, asset: FileAsset) -> bool:
    # Multi-turn scenario recordings are not represented by a legacy Attempt.
    # Resolve them through their dialogue session so assigned therapists can replay
    # the exact turn they are reviewing.
    from app.modules.scenario_dialogues.model import ScenarioDialogueSession, ScenarioDialogueTurn

    profile_id = db.scalar(
        select(TrainingSession.patient_profile_id)
        .join(SessionTask, SessionTask.training_session_id == TrainingSession.id)
        .join(Attempt, Attempt.session_task_id == SessionTask.id)
        .where(Attempt.audio_file_id == asset.id)
        .limit(1)
    )
    if not profile_id:
        profile_id = db.scalar(
            select(TrainingSession.patient_profile_id)
            .join(ScenarioDialogueSession, ScenarioDialogueSession.training_session_id == TrainingSession.id)
            .join(ScenarioDialogueTurn, ScenarioDialogueTurn.dialogue_session_id == ScenarioDialogueSession.id)
            .where(ScenarioDialogueTurn.audio_file_id == asset.id)
            .limit(1)
        )
    if not profile_id:
        return False
    return can_access_patient_profile_file(db, user, profile_id)


def can_access_patient_profile_file(db: Session, user: User, patient_profile_id) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.therapist:
        return bool(
            db.scalar(
                select(TherapistPatientAssignment.id)
                .where(
                    TherapistPatientAssignment.therapist_user_id == user.id,
                    TherapistPatientAssignment.patient_profile_id == patient_profile_id,
                    TherapistPatientAssignment.status == "active",
                )
                .limit(1)
            )
        )
    if user.role != UserRole.family:
        return False
    return bool(
        db.scalar(
            select(PatientProfile.id)
            .join(FamilyPatientBinding, FamilyPatientBinding.patient_profile_id == PatientProfile.id)
            .where(
                PatientProfile.id == patient_profile_id,
                FamilyPatientBinding.family_user_id == user.id,
                FamilyPatientBinding.status == "active",
            )
            .limit(1)
        )
    )
