from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.files.model import FileAsset, FileType
from app.modules.users.model import User


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
    if not asset or asset.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return asset
