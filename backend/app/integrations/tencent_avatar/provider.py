from __future__ import annotations

from app.core.config import get_settings


class TencentAvatarError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def is_configured() -> bool:
    settings = get_settings()
    # The browser H5 SDK authenticates with a short-lived sign. For the first
    # wiring test it can be pasted from the Tencent console into .env; the
    # production implementation should replace this with a server-side signer.
    return bool(
        settings.tencent_avatar_enabled
        and settings.tencent_avatar_sign
        and settings.tencent_avatar_asset_virtualman_key
    )


def create_browser_session(*, user_id: str) -> dict[str, object]:
    if not is_configured():
        raise TencentAvatarError(
            "not_configured",
            "腾讯云数字人尚未启用，或缺少 TENCENT_AVATAR_SIGN / TENCENT_AVATAR_ASSET_VIRTUALMAN_KEY。",
        )
    settings = get_settings()
    return {
        "provider": "tencent",
        # The H5 SDK creates the actual provider session in the browser. The
        # local lease id is returned separately by the avatar session service.
        "session_id": "browser-created",
        "sign": settings.tencent_avatar_sign,
        "asset_virtualman_key": settings.tencent_avatar_asset_virtualman_key,
        "user_id": f"{settings.tencent_avatar_user_id_prefix}{user_id}",
        "protocol": settings.tencent_avatar_protocol,
        "driver_type": settings.tencent_avatar_driver_type,
    }
