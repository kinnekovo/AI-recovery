from pathlib import Path
from shutil import which

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.response import api_success
from app.database.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    return api_success(
        {
            "status": "ok",
            "database": database_status(db),
            "storage": storage_status(settings.storage_root),
            "providers": provider_statuses(settings),
        }
    )


def database_status(db: Session) -> dict[str, str]:
    try:
        db.execute(text("select 1"))
    except Exception:
        return {"status": "unavailable"}
    return {"status": "ok"}


def storage_status(root: Path) -> dict[str, str | bool]:
    return {
        "status": "ok" if root.exists() else "missing",
        "root": str(root),
        "exists": root.exists(),
        "is_dir": root.is_dir(),
    }


def provider_statuses(settings) -> dict[str, dict[str, str | list[str] | bool]]:
    return {
        "speech_eval": provider_status("speech_eval", settings.speech_eval_provider, []),
        "asr": provider_status(
            "asr",
            settings.asr_provider,
            tencent_asr_missing_env(settings) if settings.asr_provider == "tencent" else [],
        ),
        "acoustic": provider_status(
            "acoustic",
            settings.acoustic_provider,
            acoustic_missing_env(settings) if settings.acoustic_provider == "local" else [],
        ),
        "pronunciation": provider_status(
            "pronunciation",
            settings.pronunciation_provider,
            tencent_soe_missing_env(settings) if settings.pronunciation_provider == "tencent_soe" else [],
        ),
        "tts": provider_status(
            "tts",
            settings.tts_provider,
            required_missing(settings, {"TTS_API_KEY": settings.tts_api_key, "TTS_BASE_URL": settings.tts_base_url})
            if settings.tts_provider != "mock"
            else [],
        ),
        "llm_feedback": provider_status(
            "llm_feedback",
            settings.llm_feedback_provider,
            required_missing(
                settings,
                {
                    "LLM_FEEDBACK_API_KEY": settings.llm_feedback_api_key,
                    "LLM_FEEDBACK_BASE_URL": settings.llm_feedback_base_url,
                    "LLM_FEEDBACK_MODEL": settings.llm_feedback_model,
                },
            )
            if settings.llm_feedback_provider != "mock"
            else [],
        ),
    }


def provider_status(name: str, provider: str, missing_env: list[str]) -> dict[str, str | list[str] | bool]:
    if provider == "disabled":
        return {
            "name": name,
            "provider": provider,
            "mode": "disabled",
            "status": "disabled",
            "ready": False,
            "missing_env": [],
            "message": "精细发音评测未启用，不会生成模拟分数。",
        }
    if provider == "mock":
        return {
            "name": name,
            "provider": provider,
            "mode": "mock",
            "status": "ok",
            "ready": True,
            "missing_env": [],
            "message": "使用 mock provider，可用于流程演示。",
        }
    if missing_env:
        return {
            "name": name,
            "provider": provider,
            "mode": "external",
            "status": "config_missing",
            "ready": False,
            "missing_env": missing_env,
            "message": "外部 provider 配置不完整，运行时会回退或失败。",
        }
    return {
        "name": name,
        "provider": provider,
        "mode": "external",
        "status": "configured",
        "ready": True,
        "missing_env": [],
        "message": "外部 provider 配置已填写，仍需通过真实调用验证。",
    }


def tencent_asr_missing_env(settings) -> list[str]:
    return required_missing(
        settings,
        {
            "TENCENTCLOUD_SECRET_ID": settings.tencentcloud_secret_id,
            "TENCENTCLOUD_SECRET_KEY": settings.tencentcloud_secret_key,
        },
    )


def tencent_soe_missing_env(settings) -> list[str]:
    return required_missing(
        settings,
        {
            "TENCENTCLOUD_SECRET_ID": settings.tencentcloud_secret_id,
            "TENCENTCLOUD_SECRET_KEY": settings.tencentcloud_secret_key,
            "TENCENT_SOE_APP_ID": settings.tencent_soe_app_id,
        },
    )


def acoustic_missing_env(settings) -> list[str]:
    ffmpeg = settings.ffmpeg_bin or which("ffmpeg")
    if ffmpeg:
        return []
    try:
        import imageio_ffmpeg

        return [] if imageio_ffmpeg.get_ffmpeg_exe() else ["FFMPEG_BIN"]
    except ImportError:
        return ["FFMPEG_BIN"]


def required_missing(settings, values: dict[str, str | None]) -> list[str]:
    return [name for name, value in values.items() if not value]
