from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.tts.provider import get_tts_provider
from app.integrations.voice_clone.provider import VoiceCloneProviderError, VoiceCloneTaskStatus, get_voice_clone_provider
from app.modules.agents.model import Agent, AgentGenerationStatus, AliyunAvatarStatus
from app.modules.agents.schema import AgentCreate
from app.modules.consent.service import record_consent, require_active_consent
from app.modules.files.model import FileAsset, FileStatus, FileType
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
        avatar_gender=payload.avatar_gender,
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


def upload_avatar(db: Session, user: User, agent_id: UUID, upload: UploadFile, animation_config: dict | None = None) -> Agent:
    agent = get_owned_agent(db, user, agent_id)
    record_consent(db, user, agent.id, "image")
    asset = save_upload(db, user, upload, FileType.agent_image)
    agent.avatar_file_id = asset.id
    agent.avatar_animation_config = animation_config
    agent.image_consent_confirmed = True
    agent.aliyun_avatar_id = None
    agent.aliyun_chat_config_id = None
    agent.aliyun_avatar_source_file_id = None
    agent.aliyun_avatar_status = AliyunAvatarStatus.pending
    agent.aliyun_avatar_error = None
    db.commit()
    db.refresh(agent)
    settings = get_settings()
    if settings.aliyun_avatar_enabled and settings.aliyun_avatar_auto_provision:
        # Provisioning is deliberately best-effort: a provider failure must not
        # discard the patient's local 2.5D avatar upload.
        try:
            from app.modules.avatar_sessions.service import ensure_agent_provisioned

            return ensure_agent_provisioned(db, user, agent)
        except HTTPException:
            db.refresh(agent)
    return agent


def get_voice_training_text(db: Session, user: User, agent_id: UUID, *, refresh: bool = False) -> Agent:
    agent = get_owned_agent(db, user, agent_id)
    require_active_consent(db, user, agent.id, "voice")
    if agent.voice_external_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该智能体已有专属音色，不能再申请新的音色 ID。")
    if agent.voice_clone_task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该智能体已创建声音复刻任务，只能查询该任务，不能创建新的音色 ID。")
    if agent.voice_training_text_id and agent.voice_training_text and not refresh:
        return agent
    try:
        training = get_voice_clone_provider().get_training_text()
    except VoiceCloneProviderError as exc:
        raise _voice_clone_http_error(exc) from exc
    agent.voice_training_text_id = training.text_id
    agent.voice_training_text = training.text
    db.commit()
    db.refresh(agent)
    return agent


def delete_owned_agent(db: Session, user: User, agent_id: UUID) -> UUID | None:
    """Remove one companion while retaining de-identified training history."""
    profile = get_patient_profile(db, user)
    agent = get_owned_agent(db, user, agent_id)
    replacement_id = db.scalar(
        select(Agent.id)
        .where(Agent.patient_profile_id == profile.id, Agent.id != agent.id)
        .order_by(Agent.created_at.desc())
        .limit(1)
    )
    if profile.current_agent_id == agent.id:
        profile.current_agent_id = replacement_id
        profile.onboarding_status = OnboardingStatus.ready if replacement_id else OnboardingStatus.pending_agent

    from app.modules.consent.model import ConsentRecord
    from app.modules.training.model import TrainingSession

    db.execute(update(TrainingSession).where(TrainingSession.agent_id == agent.id).values(agent_id=None))
    db.execute(delete(ConsentRecord).where(ConsentRecord.agent_id == agent.id))
    from app.modules.avatar_sessions.model import AvatarSession
    db.execute(delete(AvatarSession).where(AvatarSession.agent_id == agent.id))
    for file_id in (agent.avatar_file_id, agent.voice_sample_file_id, agent.welcome_audio_file_id):
        if file_id:
            asset = db.get(FileAsset, file_id)
            if asset and asset.owner_user_id == user.id:
                asset.status = FileStatus.deleted
    db.delete(agent)
    db.commit()
    return replacement_id


def upload_voice_sample(db: Session, user: User, agent_id: UUID, upload: UploadFile, voice_gender: int) -> Agent:
    agent = get_owned_agent(db, user, agent_id)
    require_active_consent(db, user, agent.id, "voice")
    if agent.voice_external_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该智能体已有专属音色，不能再上传音频或创建新的音色 ID。")
    if agent.voice_clone_task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该智能体已创建声音复刻任务，只能查询该任务，不能创建新的音色 ID。")
    if not agent.voice_training_text_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="请先获取并朗读页面展示的指定文本，再上传声音样本。")
    asset = save_upload(db, user, upload, FileType.voice_sample)
    try:
        task = get_voice_clone_provider().create_one_sentence_clone(
            asset.storage_path,
            text_id=agent.voice_training_text_id,
            voice_name=agent.name,
            voice_gender=voice_gender,
        )
    except VoiceCloneProviderError as exc:
        raise _voice_clone_http_error(exc) from exc
    agent.voice_sample_file_id = asset.id
    agent.voice_clone_task_id = task.task_id
    agent.voice_consent_confirmed = True
    agent.generation_status = AgentGenerationStatus.voice_training
    db.commit()
    db.refresh(agent)
    return agent


def refresh_voice_clone_status(db: Session, user: User, agent_id: UUID) -> tuple[Agent, VoiceCloneTaskStatus]:
    agent = get_owned_agent(db, user, agent_id)
    require_active_consent(db, user, agent.id, "voice")
    if not agent.voice_clone_task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该智能体尚未创建声音复刻任务。")
    try:
        task = get_voice_clone_provider().get_task_status(agent.voice_clone_task_id)
    except VoiceCloneProviderError as exc:
        raise _voice_clone_http_error(exc) from exc
    if task.status_code == 2:
        if not task.fast_voice_type:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="腾讯云任务已完成但未返回专属音色 ID。")
        if agent.voice_external_id and agent.voice_external_id != task.fast_voice_type:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="检测到不同的专属音色 ID，已停止保存以避免覆盖。")
        agent.voice_external_id = task.fast_voice_type
        agent.generation_status = AgentGenerationStatus.voice_ready
    elif task.status_code == 3:
        agent.generation_status = AgentGenerationStatus.failed
    else:
        agent.generation_status = AgentGenerationStatus.voice_training
    db.commit()
    db.refresh(agent)
    return agent, task


def _voice_clone_http_error(exc: VoiceCloneProviderError) -> HTTPException:
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY if exc.code in {"unsupported_audio", "audio_too_large", "empty_audio", "quality_rejected"} else status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=status_code, detail=exc.message)


def generate_welcome_audio(db: Session, user: User, agent_id: UUID) -> tuple[Agent, str]:
    agent = get_owned_agent(db, user, agent_id)
    if agent.voice_external_id:
        require_active_consent(db, user, agent.id, "voice")
    text = f"{agent.name}已经准备好了，我们一起开始今天的练习。"
    audio_path = get_tts_provider().synthesize(text, agent.voice_external_id or "default")
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


def sync_aliyun_avatar(db: Session, user: User, agent_id: UUID) -> Agent:
    from app.modules.avatar_sessions.service import sync_agent

    return sync_agent(db, user, get_owned_agent(db, user, agent_id))
