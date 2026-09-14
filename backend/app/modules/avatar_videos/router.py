from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.avatar_videos import service
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/avatar-video-tasks", tags=["avatar-video-tasks"])


@router.get("/{task_id}")
def get_task(task_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.task_payload(service.get_owned_task(db, current_user, task_id)))
