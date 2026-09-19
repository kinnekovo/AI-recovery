from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
from PIL import Image

from app.core.config import get_settings


class AliyunAvatarError(Exception):
    def __init__(self, code: str, message: str, *, manual_review: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.manual_review = manual_review


def is_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.aliyun_avatar_enabled
        and settings.aliyun_avatar_instance_id
    )


def _client():
    if not is_configured():
        raise AliyunAvatarError("not_configured", "阿里云数字人尚未启用或未填写实例 ID。")
    try:
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_lingmou20250527.client import Client as LingMouClient
        from alibabacloud_tea_openapi.models import Config

        config = Config(credential=CredentialClient())
        config.endpoint = get_settings().aliyun_avatar_endpoint
        return LingMouClient(config)
    except ImportError as exc:
        raise AliyunAvatarError("sdk_missing", "阿里云数字人 SDK 未安装。") from exc


def _body(response):
    body = getattr(response, "body", response)
    if not getattr(body, "success", True):
        raise AliyunAvatarError("aliyun_rejected", getattr(body, "message", "阿里云拒绝了本次请求。"))
    return getattr(body, "data", body)


def _portrait_9x16(source_path: str) -> Path:
    """Create a temporary, upload-safe 9:16 JPEG while retaining the original locally."""
    try:
        image = Image.open(source_path).convert("RGB")
    except Exception as exc:
        raise AliyunAvatarError("invalid_image", "照片无法读取，请重新上传 JPG、PNG 或 WebP 图片。") from exc
    if min(image.size) < 400:
        raise AliyunAvatarError("image_too_small", "照片短边至少需要 400 像素。")
    ratio = 9 / 16
    width, height = image.size
    if width / height > ratio:
        crop_width = int(height * ratio)
        left = max(0, (width - crop_width) // 2)
        image = image.crop((left, 0, left + crop_width, height))
    else:
        crop_height = int(width / ratio)
        top = max(0, (height - crop_height) // 2)
        image = image.crop((0, top, width, top + crop_height))
    image = image.resize((720, 1280), Image.Resampling.LANCZOS)
    output = NamedTemporaryFile(prefix="aliyun-avatar-", suffix=".jpg", delete=False)
    output.close()
    image.save(output.name, "JPEG", quality=92, optimize=True)
    return Path(output.name)


def provision_no_train_avatar(*, name: str, gender: str, source_path: str) -> tuple[str, str]:
    """Upload a photo, create a no-train avatar and its chat configuration."""
    try:
        from alibabacloud_lingmou20250527 import models
    except ImportError as exc:
        raise AliyunAvatarError("sdk_missing", "阿里云数字人 SDK 未安装。") from exc
    client = _client()
    staged = _portrait_9x16(source_path)
    try:
        policy = _body(client.get_upload_policy(models.GetUploadPolicyRequest(type="INPUT_INFER_PIC")))
        oss_policy = getattr(policy, "oss_policy", None)
        host = getattr(oss_policy, "host", None)
        if not host or not getattr(policy, "oss_key", None) or not getattr(oss_policy, "access_id", None):
            raise AliyunAvatarError("upload_policy_invalid", "阿里云未返回完整的照片上传授权。")
        upload_key = f"{getattr(policy, 'oss_key')}/{staged.name}"
        fields = {
            "key": upload_key,
            "policy": getattr(oss_policy, "policy"),
            "OSSAccessKeyId": getattr(oss_policy, "access_id"),
            "signature": getattr(oss_policy, "signature"),
        }
        with staged.open("rb") as image_file:
            upload_url = host if str(host).startswith("http") else f"https://{host}"
            response = httpx.post(upload_url, data=fields, files={"file": (staged.name, image_file, "image/jpeg")}, timeout=30)
        response.raise_for_status()
        avatar = _body(client.create_no_train_pic_avatar(models.CreateNoTrainPicAvatarRequest(
            name=name[:80], gender=gender, image_oss_path=upload_key, transparent=False, expressiveness="NORMAL"
        )))
        avatar_id = getattr(avatar, "avatar_id", None)
        if not avatar_id or getattr(avatar, "pass_", True) is False:
            raise AliyunAvatarError("avatar_id_missing", "阿里云未返回形象 ID，请勿重复提交。", manual_review=True)
        config = _body(client.create_chat_config(models.CreateChatConfigRequest(avatar_id=avatar_id)))
        project_id = getattr(config, "id", None)
        if not project_id:
            raise AliyunAvatarError("project_id_missing", "形象已创建但未返回对话项目 ID，请勿重复提交。", manual_review=True)
        return avatar_id, project_id
    except AliyunAvatarError:
        raise
    except Exception as exc:
        raise AliyunAvatarError("provision_uncertain", "阿里云形象创建结果不确定，请在控制台确认后再人工重试。", manual_review=True) from exc
    finally:
        staged.unlink(missing_ok=True)


def create_chat_session(project_id: str) -> dict[str, object]:
    try:
        from alibabacloud_lingmou20250527 import models

        data = _body(_client().create_chat_session(project_id, models.CreateChatSessionRequest(instance_id=get_settings().aliyun_avatar_instance_id)))
        rtc = getattr(data, "rtc_params", None)
        if not getattr(data, "session_id", None) or not rtc:
            raise AliyunAvatarError("session_invalid", "阿里云未返回有效的 RTC 会话参数。")
        return {
            "session_id": data.session_id,
            "rtc_params": {key: getattr(rtc, key, None) for key in ("app_id", "channel", "timestamp", "token", "nonce", "client_user_id", "server_user_id", "avatar_user_id", "gslb")},
        }
    except AliyunAvatarError:
        raise
    except Exception as exc:
        raise AliyunAvatarError("session_create_failed", "阿里云实时会话创建失败。") from exc


def close_chat_session(session_id: str) -> None:
    if not is_configured():
        return
    try:
        from alibabacloud_lingmou20250527 import models

        _client().close_chat_instance_sessions(
            get_settings().aliyun_avatar_instance_id,
            models.CloseChatInstanceSessionsRequest(session_ids=[session_id]),
        )
    except Exception:
        # A local lease is always closed even if the provider has already expired it.
        return
