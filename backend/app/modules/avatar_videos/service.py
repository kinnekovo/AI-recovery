from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.observability import log_event
from app.integrations.avatar_video.provider import AvatarVideoProviderError, get_avatar_video_provider
from app.modules.agents.model import Agent
from app.modules.avatar_videos.model import AvatarVideoTask, AvatarVideoTaskStatus
from app.modules.files.model import FileAsset, FileStatus, FileType
from app.modules.files.service import public_url, storage_dir
from app.modules.users.model import User


def avatar_video_cache_key(agent: Agent, audio_file: FileAsset, provider_identity: str) -> str:
    avatar_version = agent.avatar_file.updated_at.isoformat() if agent.avatar_file else "missing"
    source = f"{agent.avatar_file_id}|{avatar_version}|{audio_file.id}|{provider_identity}"
    return sha256(source.encode("utf-8")).hexdigest()


def enqueue_for_audio(db: Session, user: User, agent: Agent, audio_file: FileAsset) -> AvatarVideoTask | None:
    settings = get_settings()
    if settings.avatar_video_provider == "disabled" or not agent.avatar_file_id or not agent.avatar_file:
        return None
    if not agent.image_consent_confirmed:
        return None
    provider = get_avatar_video_provider()
    cache_key = avatar_video_cache_key(agent, audio_file, provider.cache_identity())
    existing = db.scalar(
        select(AvatarVideoTask).where(
            AvatarVideoTask.owner_user_id == user.id,
            AvatarVideoTask.cache_key == cache_key,
        )
    )
    if existing:
        # A timeout or transient runtime failure must not permanently poison the
        # cache key. Retrying the same text should reuse its WAV and requeue the
        # same durable task after the operator has corrected the environment.
        if existing.status == AvatarVideoTaskStatus.failed:
            existing.status = AvatarVideoTaskStatus.queued
            existing.error_code = None
            existing.error_message = None
            existing.generation_ms = None
            db.commit()
            db.refresh(existing)
            log_event("info", "avatar_video", "task_requeued", task_id=str(existing.id), provider=provider.name)
        return existing
    task = AvatarVideoTask(
        owner_user_id=user.id,
        agent_id=agent.id,
        audio_file_id=audio_file.id,
        cache_key=cache_key,
        provider=provider.name,
        status=AvatarVideoTaskStatus.queued,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_event("info", "avatar_video", "task_queued", task_id=str(task.id), provider=provider.name)
    return task


def get_owned_task(db: Session, user: User, task_id: UUID) -> AvatarVideoTask:
    task = db.get(AvatarVideoTask, task_id)
    if not task or task.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="动态形象任务不存在")
    return task


def task_payload(task: AvatarVideoTask) -> dict:
    return {
        "id": task.id,
        "status": task.status.value,
        "video_url": public_url(task.video_file) if task.video_file_id and task.video_file else None,
        "error_message": task.error_message,
        "generation_ms": task.generation_ms,
        "created_at": task.created_at,
    }


def claim_next_task(db: Session) -> AvatarVideoTask | None:
    task = db.scalar(
        select(AvatarVideoTask)
        .where(AvatarVideoTask.status == AvatarVideoTaskStatus.queued)
        .order_by(AvatarVideoTask.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not task:
        return None
    task.status = AvatarVideoTaskStatus.running
    task.attempt_count += 1
    task.error_code = None
    task.error_message = None
    db.commit()
    db.refresh(task)
    return task


def recover_stale_running_tasks(db: Session) -> int:
    """Mark interrupted GPU jobs as failed so they never spin forever in the UI."""
    deadline = datetime.now(timezone.utc) - timedelta(seconds=get_settings().sadtalker_timeout_seconds + 30)
    stale_tasks = list(
        db.scalars(
            select(AvatarVideoTask).where(
                AvatarVideoTask.status == AvatarVideoTaskStatus.running,
                AvatarVideoTask.updated_at < deadline,
            )
        )
    )
    for task in stale_tasks:
        task.status = AvatarVideoTaskStatus.failed
        task.error_code = "worker_interrupted"
        task.error_message = "动态形象生成被中断，已保留语音示范。"
    if stale_tasks:
        db.commit()
        log_event("warning", "avatar_video", "stale_tasks_recovered", count=len(stale_tasks))
    return len(stale_tasks)


def process_task(db: Session, task: AvatarVideoTask) -> AvatarVideoTask:
    started = perf_counter()
    try:
        _validate_task_inputs(task)
        provider = get_avatar_video_provider()
        if provider.name != task.provider:
            raise AvatarVideoProviderError("provider_changed", "动态形象配置已变更，请重新请求示范。")
        temporary_dir = storage_dir(FileType.generated_avatar_video) / f".task-{task.id}-{uuid4().hex}"
        generated_path = provider.generate(Path(task.agent.avatar_file.storage_path), Path(task.audio_file.storage_path), temporary_dir)
        if not generated_path.is_file() or generated_path.stat().st_size == 0:
            raise AvatarVideoProviderError("empty_result", "动态形象未生成有效视频。")
        final_dir = storage_dir(FileType.generated_avatar_video)
        final_path = final_dir / f"avatar_{task.cache_key}.mp4"
        generated_path.replace(final_path)
        asset = FileAsset(
            owner_user_id=task.owner_user_id,
            file_type=FileType.generated_avatar_video,
            original_name=final_path.name,
            storage_path=str(final_path),
            mime_type="video/mp4",
            size_bytes=final_path.stat().st_size,
        )
        db.add(asset)
        db.flush()
        task.video_file_id = asset.id
        task.status = AvatarVideoTaskStatus.succeeded
        task.generation_ms = int((perf_counter() - started) * 1000)
        task.error_code = None
        task.error_message = None
        db.commit()
        db.refresh(task)
        log_event("info", "avatar_video", "task_succeeded", task_id=str(task.id), generation_ms=task.generation_ms)
        return task
    except AvatarVideoProviderError as exc:
        return mark_task_failed(db, task, exc.code, exc.message, started)
    except Exception as exc:
        log_event("error", "avatar_video", "task_failed_unexpected", task_id=str(task.id), error=exc)
        return mark_task_failed(db, task, "generation_failed", "动态形象生成失败，已保留语音示范。", started)


def mark_task_failed(db: Session, task: AvatarVideoTask, code: str, message: str, started: float | None = None) -> AvatarVideoTask:
    task.status = AvatarVideoTaskStatus.failed
    task.error_code = code
    task.error_message = message[:300]
    task.generation_ms = int((perf_counter() - started) * 1000) if started is not None else None
    db.commit()
    db.refresh(task)
    log_event("warning", "avatar_video", "task_failed", task_id=str(task.id), error_code=code)
    return task


def _validate_task_inputs(task: AvatarVideoTask) -> None:
    if not task.agent or task.agent.patient_profile.user_id != task.owner_user_id:
        raise AvatarVideoProviderError("ownership_invalid", "动态形象任务归属无效。")
    if not task.agent.image_consent_confirmed or not task.agent.avatar_file_id:
        raise AvatarVideoProviderError("consent_required", "未获得有效的形象使用授权。")
    for asset in (task.agent.avatar_file, task.audio_file):
        if not asset or asset.status != FileStatus.active or not Path(asset.storage_path).is_file():
            raise AvatarVideoProviderError("input_missing", "动态形象所需的头像或音频已不可用。")


def invalidate_agent_video_tasks(db: Session, agent_id: UUID, owner_user_id: UUID) -> None:
    """Make generated portrait videos inaccessible after image consent is withdrawn or an agent is removed."""
    tasks = list(
        db.scalars(
            select(AvatarVideoTask).where(
                AvatarVideoTask.agent_id == agent_id,
                AvatarVideoTask.owner_user_id == owner_user_id,
            )
        )
    )
    for task in tasks:
        if task.video_file and task.video_file.owner_user_id == owner_user_id:
            task.video_file.status = FileStatus.deleted
        if task.status in {AvatarVideoTaskStatus.queued, AvatarVideoTaskStatus.running}:
            task.status = AvatarVideoTaskStatus.failed
            task.error_code = "image_consent_revoked"
            task.error_message = "形象授权已撤回，动态形象任务已停止。"
