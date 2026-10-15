from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.agents.service import get_owned_agent
from app.modules.avatar_sessions import service
from app.modules.avatar_sessions.schema import AvatarSessionCreate, AvatarSpeechCreate, AvatarTextDrive
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/avatar/sessions", tags=["avatar-sessions"])


@router.post("")
def create(payload: AvatarSessionCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    if payload.provider not in {"aliyun", "tencent"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的数字人服务商。")
    agent = get_owned_agent(db, current_user, payload.agent_id) if payload.agent_id else None
    if payload.provider == "aliyun" and agent is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="阿里云数字人需要绑定智能体。")
    lease, result = service.create_session(db, current_user, agent, provider=payload.provider)
    return api_success({"id": str(lease.id), **result})


@router.post("/speech")
def create_speech(payload: AvatarSpeechCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    agent = get_owned_agent(db, current_user, payload.agent_id) if payload.agent_id else None
    return api_success(service.generate_speech(db, current_user, agent, payload.text))


@router.delete("/{session_id}")
def close(session_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    service.close_session(db, current_user, service.get_owned_session(db, current_user, session_id))
    return api_success({"closed": True})


@router.post("/{session_id}/audio")
def drive_audio(
    session_id: UUID,
    audio: bytes = Body(..., media_type="application/octet-stream"),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.drive_audio(db, current_user, service.get_owned_session(db, current_user, session_id), audio)
    return api_success(result)


@router.post("/{session_id}/text")
def drive_text(
    session_id: UUID,
    payload: AvatarTextDrive,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.drive_text(db, current_user, service.get_owned_session(db, current_user, session_id), payload.text)
    return api_success(result)
