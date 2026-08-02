from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.files import service
from app.modules.files.model import FileType
from app.modules.files.schema import FileRead
from app.modules.users.model import User
from app.modules.users.service import get_current_user

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
def upload_file(
    file_type: FileType,
    upload_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = service.save_upload(db, current_user, upload_file, file_type)
    return api_success({"file": FileRead.model_validate(asset).model_dump(mode="json"), "url": service.public_url(asset)})


@router.get("/{file_id}/content")
def get_file_content(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = service.get_accessible_file(db, current_user, file_id)
    return FileResponse(asset.storage_path, media_type=asset.mime_type, filename=asset.original_name)
