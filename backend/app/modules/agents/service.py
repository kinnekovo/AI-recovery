from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.tts.provider import get_tts_provider
from app.integrations.voice_clone.provider import get_voice_clone_provider
from app.modules.agents.model import Agent, AgentGenerationStatus
from app.modules.agents.schema import AgentCreate
from app.modules.consent.service import record_consent
from app.modules.files.model import FileAsset, FileType
from app.modules.files.service import public_url, save_upload
from app.modules.users.model import OnboardingStatus, User
from app.modules.users.service import get_patient_profile


def create_agent(db: Session, user: User, payload: AgentCreate) -> Agent:
    profile = get_patient_profile(db, user)
    agent = Agent(
        patient_profile_id=profile.id,
        name=payload.name,
        relationship=payload.relationship,
        personality_style=payload.personality_style,
        image_consent_confirmed=payload.image_consent_confirmed,
        voice_consent_confirmed=payload.voice_consent_confirmed,
    )
    db.add(agent)
    db.flush()
    if payload.image_consent_confirmed:
        record_consent(db, user, agent.id, "image")
    if payload.voice_consent_confirmed:
        record_consent(db, user, agent.id, "voice")
    if profile.current_agent_id is None:
        profile.current_agent_id = agent.id
        profile.onboarding_status = OnboardingStatus.ready
    db.commit()
    db.refresh(agent)
    return agent


def list_agents(db: Session, user: User) -> list[Agent]:
    profile = get_patient_profile(db, user)
    return list(db.scalars(select(Agent).where(Agent.patient_profile_id == profile.id).order_by(Agent.created_at.desc())))


def get_owned_agent(db: Session, user: User, agent_id: UUID) -> Agent:
    profile = get_patient_profile(db, user)
    agent = db.get(Agent, agent_id)
    if not agent or agent.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    return agent


def upload_avatar(db: Session, user: User, agent_id: UUID, upload: UploadFile) -> Agent:
    agent = get_owned_agent(db, user, agent_id)
    asset = save_upload(db, user, upload, FileType.agent_image)
    agent.avatar_file_id = asset.id
    agent.image_consent_confirmed = True
    db.commit()
    db.refresh(agent)
    return agent


def upload_voice_sample(db: Session, user: User, agent_id: UUID, upload: UploadFile) -> Agent:
    agent = get_owned_agent(db, user, agent_id)
    asset = save_upload(db, user, upload, FileType.voice_sample)
    voice_id = get_voice_clone_provider().clone_voice(asset.storage_path)
    agent.voice_sample_file_id = asset.id
    agent.voice_external_id = voice_id
    agent.voice_consent_confirmed = True
    agent.generation_status = AgentGenerationStatus.voice_ready
    db.commit()
    db.refresh(agent)
    return agent


def generate_welcome_audio(db: Session, user: User, agent_id: UUID) -> tuple[Agent, str]:
    agent = get_owned_agent(db, user, agent_id)
    if not agent.voice_external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传声音样本")
    text = f"{agent.name}已经准备好了，我们一起开始今天的练习。"
    audio_path = get_tts_provider().synthesize(text, agent.voice_external_id)
    asset = FileAsset(
        owner_user_id=user.id,
        file_type=FileType.generated_audio,
        original_name=Path(audio_path).name,
        storage_path=audio_path,
        mime_type="audio/wav",
        size_bytes=Path(audio_path).stat().st_size,
    )
    db.add(asset)
    db.flush()
    agent.welcome_audio_file_id = asset.id
    agent.generation_status = AgentGenerationStatus.ready
    db.commit()
    db.refresh(agent)
    return agent, public_url(asset)
