from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
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


@router.post("/{agent_id}/avatar")
def upload_avatar(
    agent_id: UUID,
    avatar_file: UploadFile = File(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.upload_avatar(db, current_user, agent_id, avatar_file)
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/voice")
def upload_voice(
    agent_id: UUID,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent = service.upload_voice_sample(db, current_user, agent_id, audio_file)
    return api_success(agent_payload(agent))


@router.post("/{agent_id}/welcome-audio")
def welcome_audio(
    agent_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    agent, audio_url = service.generate_welcome_audio(db, current_user, agent_id)
    return api_success({"agent": agent_payload(agent), "audio_url": audio_url})
