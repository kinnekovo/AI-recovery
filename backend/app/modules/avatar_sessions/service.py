from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.observability import log_event
from app.integrations.aliyun_avatar.provider import AliyunAvatarError, close_chat_session, create_chat_session, is_configured, provision_no_train_avatar
from app.integrations.tts.provider import TTSProviderError, get_tts_provider
from app.integrations.tencent_avatar.provider import (
    TencentAvatarError,
    close_runtime as close_tencent_runtime,
    create_cloud_session,
    drive_audio as drive_tencent_audio,
    is_configured as tencent_is_configured,
    register_runtime,
)
from app.modules.agents.model import Agent, AliyunAvatarStatus
from app.modules.avatar_sessions.model import AvatarSession, AvatarSessionStatus
from app.modules.consent.service import require_active_consent
from app.modules.files.model import FileAsset, FileStatus, FileType
from app.modules.files.service import public_url
from app.modules.users.model import User


def provider_enabled() -> bool:
    return get_settings().aliyun_avatar_enabled and is_configured()


def ensure_agent_provisioned(db: Session, user: User, agent: Agent, *, explicit_retry: bool = False) -> Agent:
    settings = get_settings()
    if agent.aliyun_avatar_status == AliyunAvatarStatus.ready and agent.aliyun_chat_config_id:
        return agent
    if not settings.aliyun_avatar_auto_provision and not explicit_retry:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="阿里云形象尚未同步；开通后请启用自动同步或手动重试。")
    if not provider_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="阿里云数字人尚未启用。")
    if agent.aliyun_avatar_status == AliyunAvatarStatus.manual_review and not explicit_retry:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该形象的创建结果需要人工确认，不能自动重复提交。")
    if not agent.avatar_file or not agent.avatar_file_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传陪伴者照片。")
    if agent.avatar_gender not in {"MALE", "FEMALE"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请为陪伴者选择形象性别后再同步。")
    require_active_consent(db, user, agent.id, "image")
    agent.aliyun_avatar_status = AliyunAvatarStatus.provisioning
    agent.aliyun_avatar_error = None
    db.commit()
    try:
        avatar_id, project_id = provision_no_train_avatar(
            name=agent.name,
            gender=agent.avatar_gender,
            source_path=agent.avatar_file.storage_path,
        )
    except AliyunAvatarError as exc:
        agent.aliyun_avatar_status = AliyunAvatarStatus.manual_review if exc.manual_review else AliyunAvatarStatus.failed
        agent.aliyun_avatar_error = exc.message[:300]
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    agent.aliyun_avatar_id = avatar_id
    agent.aliyun_chat_config_id = project_id
    agent.aliyun_avatar_source_file_id = agent.avatar_file_id
    agent.aliyun_avatar_status = AliyunAvatarStatus.ready
    agent.aliyun_avatar_error = None
    db.commit()
    db.refresh(agent)
    return agent


def sync_agent(db: Session, user: User, agent: Agent) -> Agent:
    if not provider_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="阿里云数字人尚未启用；不会提交照片。")
    return ensure_agent_provisioned(db, user, agent, explicit_retry=True)


def create_session(db: Session, user: User, agent: Agent | None, *, provider: str = "aliyun") -> tuple[AvatarSession, dict[str, object]]:
    if provider == "tencent":
        return create_tencent_session(db, user, agent)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="阿里云数字人需要绑定智能体。")
    if not provider_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="阿里云数字人尚未启用，当前将继续使用本地形象。")
    agent = ensure_agent_provisioned(db, user, agent)
    instance_id = get_settings().aliyun_avatar_instance_id
    active = db.scalar(
        select(AvatarSession).where(
            AvatarSession.instance_id == instance_id,
            AvatarSession.status.in_([AvatarSessionStatus.opening, AvatarSessionStatus.active]),
        )
    )
    if active:
        if active.owner_user_id == user.id and active.provider_session_id:
            close_session(db, user, active)
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="数字人正在被其他会话使用，请稍后再试。")
    lease = AvatarSession(owner_user_id=user.id, agent_id=agent.id, instance_id=instance_id, status=AvatarSessionStatus.opening)
    db.add(lease)
    db.commit()
    try:
        result = create_chat_session(agent.aliyun_chat_config_id or "")
    except AliyunAvatarError as exc:
        lease.status = AvatarSessionStatus.failed
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    lease.provider_session_id = str(result["session_id"])
    lease.status = AvatarSessionStatus.active
    db.commit()
    db.refresh(lease)
    return lease, result


def create_tencent_session(db: Session, user: User, agent: Agent | None) -> tuple[AvatarSession, dict[str, object]]:
    settings = get_settings()
    asset_virtualman_key = (
        agent.tencent_avatar_virtualman_key
        if agent is not None and agent.tencent_avatar_status == "ready" and agent.tencent_avatar_virtualman_key
        else settings.tencent_avatar_asset_virtualman_key
    )
    if not tencent_is_configured(asset_virtualman_key):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="腾讯云数字人尚未启用；请配置 AppKey、AccessToken 和 AssetVirtualmanKey。",
        )
    # A configured shared/trial asset can be tested before the patient creates
    # a personal agent. Personal assets still retain the existing consent gate.
    if agent is not None:
        require_active_consent(db, user, agent.id, "image")
    instance_id = f"tencent:{asset_virtualman_key}"
    active = db.scalar(
        select(AvatarSession).where(
            AvatarSession.instance_id == instance_id,
            AvatarSession.status.in_([AvatarSessionStatus.opening, AvatarSessionStatus.active]),
        )
    )
    if active:
        if active.owner_user_id == user.id:
            close_session(db, user, active)
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="数字人正在被其他会话使用，请稍后再试。")
    lease = AvatarSession(owner_user_id=user.id, agent_id=agent.id if agent else None, instance_id=instance_id, status=AvatarSessionStatus.opening)
    db.add(lease)
    db.commit()
    try:
        result, runtime = create_cloud_session(user_id=str(user.id), asset_virtualman_key=asset_virtualman_key)
    except TencentAvatarError as exc:
        lease.status = AvatarSessionStatus.failed
        db.commit()
        log_event(
            "warning",
            "avatar_session",
            "tencent_session_create_failed",
            error_code=exc.code,
            error_message=exc.message,
            agent_id=str(agent.id) if agent else None,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    lease.provider_session_id = result.session_id
    lease.status = AvatarSessionStatus.active
    db.commit()
    db.refresh(lease)
    register_runtime(str(lease.id), runtime)
    return lease, {
        "provider": "tencent",
        "session_id": result.session_id,
        "play_stream_addr": result.play_stream_addr,
        "protocol": result.protocol,
    }


def drive_audio(db: Session, user: User, lease: AvatarSession, pcm_data: bytes) -> dict[str, object]:
    if lease.owner_user_id != user.id or not lease.instance_id.startswith("tencent:"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="腾讯云数字人会话不存在。")
    if lease.status != AvatarSessionStatus.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="腾讯云数字人会话尚未就绪。")
    try:
        return drive_tencent_audio(str(lease.id), pcm_data)
    except TencentAvatarError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc


def generate_speech(db: Session, user: User, agent: Agent | None, text: str) -> dict[str, object]:
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本不能为空。")
    if len(clean_text) > 150:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数字人口播文本不能超过 150 个字符。")
    try:
        provider = get_tts_provider()
    except TTSProviderError as exc:
        log_event("warning", "avatar_speech", "speech_provider_unavailable", error_code=exc.code)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    voice_id = agent.voice_external_id if agent and agent.voice_external_id else "default"
    fallback = agent is None or agent.voice_external_id is None
    if agent and agent.voice_external_id:
        require_active_consent(db, user, agent.id, "voice")
    cache_name = _speech_cache_name(provider.cache_identity(voice_id), clean_text)
    cached = db.scalar(
        select(FileAsset).where(
            FileAsset.owner_user_id == user.id,
            FileAsset.file_type == FileType.generated_audio,
            FileAsset.original_name == cache_name,
            FileAsset.status == FileStatus.active,
        )
    )
    if cached and Path(cached.storage_path).is_file() and Path(cached.storage_path).stat().st_size > 0:
        return {
            "text": clean_text,
            "audio_file_id": str(cached.id),
            "audio_url": public_url(cached),
            "provider": provider.name,
            "fallback": fallback,
            "cached": True,
        }

    try:
        audio_path = provider.synthesize(clean_text, voice_id)
    except TTSProviderError as exc:
        log_event("warning", "avatar_speech", "speech_generation_failed", error_code=exc.code)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    path = Path(audio_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="数字人口播音频生成失败。")
    cache_path = path.with_name(cache_name)
    if path != cache_path:
        path.replace(cache_path)
        path = cache_path
    asset = FileAsset(
        owner_user_id=user.id,
        file_type=FileType.generated_audio,
        original_name=path.name,
        storage_path=str(path),
        mime_type="audio/wav",
        size_bytes=path.stat().st_size,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "text": clean_text,
        "audio_file_id": str(asset.id),
        "audio_url": public_url(asset),
        "provider": provider.name,
        "fallback": fallback,
        "cached": False,
    }


def _speech_cache_name(provider_identity: str, text: str) -> str:
    digest = sha256(f"{provider_identity}|{text}".encode("utf-8")).hexdigest()
    return f"avatar_{digest}.wav"


def close_session(db: Session, user: User, lease: AvatarSession) -> None:
    if lease.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数字人会话不存在。")
    if lease.status == AvatarSessionStatus.closed:
        return
    if lease.instance_id.startswith("tencent:"):
        close_tencent_runtime(str(lease.id), lease.provider_session_id)
    elif lease.provider_session_id:
        close_chat_session(lease.provider_session_id)
    lease.status = AvatarSessionStatus.closed
    db.commit()


def get_owned_session(db: Session, user: User, session_id: UUID) -> AvatarSession:
    lease = db.get(AvatarSession, session_id)
    if not lease or lease.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数字人会话不存在。")
    return lease
