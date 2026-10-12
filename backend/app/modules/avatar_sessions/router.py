from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.agents.service import get_owned_agent
from app.modules.avatar_sessions import service
from app.modules.avatar_sessions.schema import AvatarSessionCreate
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/avatar/sessions", tags=["avatar-sessions"])


@router.post("")
def create(payload: AvatarSessionCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    agent = get_owned_agent(db, current_user, payload.agent_id)
    if payload.provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的数字人服务商。")
    lease, result = service.create_session(db, current_user, agent, provider=payload.provider)
    return api_success({"id": str(lease.id), **result})


@router.delete("/{session_id}")
def close(session_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    service.close_session(db, current_user, service.get_owned_session(db, current_user, session_id))
    return api_success({"closed": True})
