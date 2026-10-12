from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.aliyun_avatar.provider import AliyunAvatarError, close_chat_session, create_chat_session, is_configured, provision_no_train_avatar
from app.integrations.tencent_avatar.provider import TencentAvatarError, create_browser_session, is_configured as tencent_is_configured
from app.modules.agents.model import Agent, AliyunAvatarStatus
from app.modules.avatar_sessions.model import AvatarSession, AvatarSessionStatus
from app.modules.consent.service import require_active_consent
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


def create_session(db: Session, user: User, agent: Agent, *, provider: str = "aliyun") -> tuple[AvatarSession, dict[str, object]]:
    if provider == "tencent":
        return create_tencent_session(db, user, agent)
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


def create_tencent_session(db: Session, user: User, agent: Agent) -> tuple[AvatarSession, dict[str, object]]:
    if not tencent_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="腾讯云数字人尚未启用；请配置 TENCENT_AVATAR_ENABLED、TENCENT_AVATAR_SIGN 和 TENCENT_AVATAR_ASSET_VIRTUALMAN_KEY。",
        )
    # A Tencent asset is cloud-rendered and represents the patient's image;
    # keep the existing consent gate before returning a browser sign.
    require_active_consent(db, user, agent.id, "image")
    settings = get_settings()
    instance_id = f"tencent:{settings.tencent_avatar_asset_virtualman_key}"
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
    lease = AvatarSession(owner_user_id=user.id, agent_id=agent.id, instance_id=instance_id, status=AvatarSessionStatus.opening)
    db.add(lease)
    db.commit()
    try:
        result = create_browser_session(user_id=str(user.id))
    except TencentAvatarError as exc:
        lease.status = AvatarSessionStatus.failed
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    lease.status = AvatarSessionStatus.active
    db.commit()
    db.refresh(lease)
    return lease, result


def close_session(db: Session, user: User, lease: AvatarSession) -> None:
    if lease.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数字人会话不存在。")
    if lease.status == AvatarSessionStatus.closed:
        return
    if lease.provider_session_id:
        close_chat_session(lease.provider_session_id)
    lease.status = AvatarSessionStatus.closed
    db.commit()


def get_owned_session(db: Session, user: User, session_id: UUID) -> AvatarSession:
    lease = db.get(AvatarSession, session_id)
    if not lease or lease.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数字人会话不存在。")
    return lease
