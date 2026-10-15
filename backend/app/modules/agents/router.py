from uuid import UUID

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.agents import service
from app.modules.agents.schema import AgentCreate, AgentRead
from app.modules.files.service import public_url
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/agents", tags=["agents"])


def agent_payload(agent) -> dict:
    payload = AgentRead.model_validate(agent).model_dump(mode="json")
    payload["avatar_url"] = public_url(agent.avatar_file) if agent.avatar_file_id and agent.avatar_file else None
    return payload


@router.post("")
def create_agent(
    payload: AgentCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.create_agent(db, current_user, payload)
    return api_success(agent_payload(agent))


@router.get("")
def list_agents(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    agents = service.list_agents(db, current_user)
    return api_success([agent_payload(agent) for agent in agents])


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    current_agent_id = service.delete_owned_agent(db, current_user, agent_id)
    return api_success({"current_agent_id": str(current_agent_id) if current_agent_id else None})


@router.post("/{agent_id}/avatar")
def upload_avatar(
    agent_id: UUID,
    avatar_file: UploadFile = File(...),
    animation_config: str | None = Form(default=None),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    config = None
    if animation_config:
        try:
            config = json.loads(animation_config)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="头像动画配置格式不正确") from exc
        if not isinstance(config, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="头像动画配置格式不正确")
    agent = service.upload_avatar(db, current_user, agent_id, avatar_file, config)
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/aliyun-avatar/sync")
def sync_aliyun_avatar(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return api_success(agent_payload(service.sync_aliyun_avatar(db, current_user, agent_id)))


@router.post("/{agent_id}/tencent-avatar/submit")
def submit_tencent_photo_avatar(
    agent_id: UUID,
    photo_version: int = Query(default=0, ge=0, le=1),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.submit_tencent_photo_avatar(db, current_user, agent_id, photo_version=photo_version)
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/tencent-avatar/status")
def refresh_tencent_photo_avatar(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return api_success(agent_payload(service.refresh_tencent_photo_avatar(db, current_user, agent_id)))


@router.post("/{agent_id}/voice")
def upload_voice(
    agent_id: UUID,
    audio_file: UploadFile = File(...),
    voice_gender: int = Form(..., ge=1, le=2),
    consent_confirmed: bool = Form(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.upload_voice_sample(
        db,
        current_user,
        agent_id,
        audio_file,
        voice_gender,
        consent_confirmed=consent_confirmed,
    )
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/voice-training-text")
def voice_training_text(
    agent_id: UUID,
    refresh: bool = Query(default=False),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.get_voice_training_text(db, current_user, agent_id, refresh=refresh)
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/voice-status")
def voice_status(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent, task = service.refresh_voice_clone_status(db, current_user, agent_id)
    return api_success(
        {
            "agent": agent_payload(agent),
            "task_status": task.status,
            "task_status_code": task.status_code,
            "error_message": task.error_message,
        }
    )


@router.post("/{agent_id}/welcome-audio")
def welcome_audio(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent, audio_url = service.generate_welcome_audio(db, current_user, agent_id)
    return api_success({"agent": agent_payload(agent), "audio_url": audio_url})
