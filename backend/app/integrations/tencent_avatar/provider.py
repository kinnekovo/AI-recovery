from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import threading
import time
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse
from uuid import uuid4

import requests
import websocket

from app.core.config import get_settings


class TencentAvatarError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _decode_response(response: requests.Response) -> dict[str, Any]:
    """Tencent responses are UTF-8 even when the response header omits charset."""
    return json.loads(response.content.decode("utf-8"))


def _api_error_message(header: dict[str, Any], fallback: str) -> str:
    message = str(header.get("Message") or fallback)
    if "AssetConcurrencyQuotaNotFound" in message:
        return (
            "腾讯云未找到与该数字人形象类型匹配的交互并发额度。"
            "IMAGE_PHOTO 资产需要开通“2D 小样本照片”交互并发。"
        )
    return message


@dataclass(frozen=True)
class TencentAvatarSessionResult:
    session_id: str
    play_stream_addr: str
    protocol: str


_runtimes: dict[str, "TencentAvatarRuntime"] = {}
_runtimes_lock = threading.Lock()


def is_configured(asset_virtualman_key: str | None = None) -> bool:
    settings = get_settings()
    return bool(
        settings.tencent_avatar_enabled
        and settings.tencent_avatar_app_key
        and settings.tencent_avatar_access_token
        and (asset_virtualman_key or settings.tencent_avatar_asset_virtualman_key)
    )


def customization_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.tencent_avatar_enabled and settings.tencent_avatar_app_key and settings.tencent_avatar_access_token)


def create_cloud_session(
    *, user_id: str, asset_virtualman_key: str | None = None, timbre_key: str | None = None
) -> tuple[TencentAvatarSessionResult, "TencentAvatarRuntime"]:
    if not is_configured(asset_virtualman_key):
        raise TencentAvatarError("not_configured", "腾讯云数字人尚未启用，或缺少 AppKey、AccessToken、AssetVirtualmanKey。")
    settings = get_settings()
    resolved_asset_key = asset_virtualman_key or settings.tencent_avatar_asset_virtualman_key or ""
    runtime = TencentAvatarRuntime(
        app_key=settings.tencent_avatar_app_key or "",
        access_token=settings.tencent_avatar_access_token or "",
        asset_virtualman_key=resolved_asset_key,
        user_id=f"{settings.tencent_avatar_user_id_prefix}{user_id}",
        protocol=settings.tencent_avatar_protocol,
        driver_type=settings.tencent_avatar_driver_type,
        base_url=settings.tencent_avatar_api_base_url,
        request_timeout=settings.tencent_avatar_request_timeout_seconds,
        ready_timeout=settings.tencent_avatar_ready_timeout_seconds,
        timbre_key=timbre_key,
    )
    try:
        return runtime.open(), runtime
    except Exception:
        runtime.close(close_cloud=True)
        raise


class TencentAvatarCustomizationClient:
    _UPLOAD_CREDENTIALS = "/v2/ivh/assetmanager/customservice/getuploadcredentials"
    _FACE_DETECT = "/v2/ivh/facedetectserver/facedetectservice/facedetect"
    _FACE_STATUS = "/v2/ivh/facedetectserver/facedetectservice/getfacedetectstate"
    _MAKE = "/v2/ivh/assetmanager/customservice/make"
    _MAKE_STATUS = "/v2/ivh/assetmanager/customservice/getprogress"
    _VOICE_TEXT = "/v2/ivh/assetmanager/zeroshotservice/gettext"
    _VOICE_DETECT = "/v2/ivh/assetmanager/zeroshotservice/detectaudioquality"
    _VOICE_DETECT_STATUS = "/v2/ivh/assetmanager/zeroshotservice/getdetectprogress"
    _TTS = "/v2/ivh/videomaker/broadcastservice/tts"
    _MEDIA_STATUS = "/v2/ivh/videomaker/broadcastservice/getprogress"

    def __init__(self) -> None:
        settings = get_settings()
        if not customization_is_configured():
            raise TencentAvatarError("not_configured", "腾讯云数智人定制尚未启用，或缺少 AppKey、AccessToken。")
        self.app_key = settings.tencent_avatar_app_key or ""
        self.access_token = settings.tencent_avatar_access_token or ""
        self.base_url = settings.tencent_avatar_api_base_url.rstrip("/")
        self.request_timeout = settings.tencent_avatar_request_timeout_seconds

    def upload_photo(self, source_path: str, crop: dict[str, object] | None = None) -> str:
        credentials_payload = self._api_call(self._UPLOAD_CREDENTIALS, {})
        credentials = credentials_payload.get("Credentials") or {}
        path_prefix = str(credentials_payload.get("PathPrefix") or "")
        secret_id = str(credentials.get("TmpSecretId") or "")
        secret_key = str(credentials.get("TmpSecretKey") or "")
        token = str(credentials.get("Token") or "")
        if not path_prefix or not secret_id or not secret_key or not token:
            raise TencentAvatarError("invalid_upload_credentials", "腾讯云没有返回完整的照片上传凭证。")

        prefix_url = path_prefix if "://" in path_prefix else f"https://{path_prefix.lstrip('/')}"
        parsed = urlparse(prefix_url)
        host = parsed.netloc
        if ".cos." not in host or not parsed.path:
            raise TencentAvatarError("invalid_upload_path", "腾讯云返回的照片上传路径格式不正确。")
        bucket, region_host = host.split(".cos.", 1)
        region = region_host.split(".myqcloud.com", 1)[0]
        key_prefix = parsed.path.strip("/")
        object_key = f"{key_prefix}/photo/{self._new_photo_filename()}"

        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:
            raise TencentAvatarError("dependency_missing", "缺少腾讯云 COS SDK，请重新安装 backend/requirements.txt。") from exc

        photo = self._prepare_photo(source_path, crop)
        try:
            config = CosConfig(
                Region=region,
                SecretId=secret_id,
                SecretKey=secret_key,
                Token=token,
                Scheme="https",
            )
            CosS3Client(config).put_object(Bucket=bucket, Body=photo, Key=object_key, ContentType="image/jpeg")
        except Exception as exc:
            raise TencentAvatarError("cos_upload_failed", f"照片上传到腾讯云失败：{exc}") from exc
        return f"https://{host}/{quote(object_key, safe='/')}"

    def upload_voice_sample(self, source_path: str, codec: str) -> str:
        credentials_payload = self._api_call(self._UPLOAD_CREDENTIALS, {})
        credentials = credentials_payload.get("Credentials") or {}
        path_prefix = str(credentials_payload.get("PathPrefix") or "")
        secret_id = str(credentials.get("TmpSecretId") or "")
        secret_key = str(credentials.get("TmpSecretKey") or "")
        token = str(credentials.get("Token") or "")
        if not path_prefix or not secret_id or not secret_key or not token:
            raise TencentAvatarError("invalid_upload_credentials", "腾讯云没有返回完整的录音上传凭证。")

        prefix_url = path_prefix if "://" in path_prefix else f"https://{path_prefix.lstrip('/')}"
        parsed = urlparse(prefix_url)
        host = parsed.netloc
        if ".cos." not in host or not parsed.path:
            raise TencentAvatarError("invalid_upload_path", "腾讯云返回的录音上传路径格式不正确。")
        bucket, region_host = host.split(".cos.", 1)
        region = region_host.split(".myqcloud.com", 1)[0]
        key_prefix = parsed.path.strip("/")
        safe_codec = codec.lower().strip(".")
        object_key = f"{key_prefix}/zeroshot/v_{uuid4().hex[:12]}.{safe_codec}"
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:
            raise TencentAvatarError("dependency_missing", "缺少腾讯云 COS SDK，请重新安装 backend/requirements.txt。") from exc
        try:
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme="https")
            with Path(source_path).open("rb") as source:
                CosS3Client(config).put_object(
                    Bucket=bucket,
                    Body=source,
                    Key=object_key,
                    ContentType=f"audio/{'mp4' if safe_codec == 'm4a' else safe_codec}",
                )
        except Exception as exc:
            raise TencentAvatarError("cos_upload_failed", f"录音上传到腾讯云失败：{exc}") from exc
        return f"https://{host}/{quote(object_key, safe='/')}"

    def get_voice_training_text(self) -> dict[str, Any]:
        return self._api_call(self._VOICE_TEXT, {"Language": "chi"})

    def start_voice_quality_detection(self, audio_url: str, *, text_id: str | None = None) -> str:
        payload: dict[str, Any] = {
            "AudioUrl": audio_url,
            "Language": "chi",
        }
        if text_id:
            payload["TextId"] = text_id
        result = self._api_call(self._VOICE_DETECT, payload)
        task_id = str(result.get("TaskId") or "")
        if not task_id:
            raise TencentAvatarError("invalid_response", "腾讯云音质检测没有返回任务 ID。")
        return task_id

    def get_voice_quality_detection(self, task_id: str) -> dict[str, Any]:
        return self._api_call(self._VOICE_DETECT_STATUS, {"TaskId": task_id})

    def start_voice_customization(self, *, audio_id: str, anchor_name: str, sex_type: str) -> str:
        result = self._api_call(self._MAKE, {
            "AnchorName": self._safe_anchor_name(anchor_name),
            "MakeType": "ZERO_SHOT_VOICE",
            "AudioId": audio_id,
            "SexType": sex_type,
            "ZeroshortLang": "chi",
            "Notes": "言语康复智能体用户授权声音复刻",
        })
        task_id = str(result.get("TaskId") or "")
        if not task_id:
            raise TencentAvatarError("invalid_response", "腾讯云声音复刻没有返回任务 ID。")
        return task_id

    def synthesize_timbre_audio(self, text: str, timbre_key: str) -> str:
        result = self._api_call(self._TTS, {
            "TimbreKey": timbre_key,
            "InputSsml": text,
            "Speed": 0.9,
            "Volume": 0,
        })
        task_id = str(result.get("TaskId") or "")
        if not task_id:
            raise TencentAvatarError("invalid_response", "腾讯云音频制作没有返回任务 ID。")
        deadline = time.monotonic() + max(60, self.request_timeout * 4)
        media_url = ""
        while time.monotonic() < deadline:
            progress = self._api_call(self._MEDIA_STATUS, {"TaskId": task_id})
            state = str(progress.get("Status") or "").upper()
            if state == "SUCCESS":
                media_url = str(progress.get("MediaUrl") or "")
                break
            if state == "FAIL":
                raise TencentAvatarError(
                    str(progress.get("FailCode") or "tts_failed"),
                    str(progress.get("FailMessage") or "腾讯云专属音色合成失败。"),
                )
            time.sleep(1)
        if not media_url:
            raise TencentAvatarError("tts_timeout", "腾讯云专属音色合成超时，请稍后重试。")
        try:
            response = requests.get(media_url, timeout=self.request_timeout)
            response.raise_for_status()
            audio_bytes = response.content
        except requests.RequestException as exc:
            raise TencentAvatarError("audio_download_failed", f"腾讯云专属音频下载失败：{exc}") from exc
        if not audio_bytes:
            raise TencentAvatarError("empty_audio", "腾讯云专属音色返回了空音频。")
        output_dir = get_settings().storage_root / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"tencent_avatar_tts_{uuid4().hex}.mp3"
        output_path.write_bytes(audio_bytes)
        return str(output_path)

    def start_face_detection(self, image_url: str, *, checker_version: int = 1) -> str:
        request_id = str(uuid4())
        result = self._api_call(self._FACE_DETECT, {
            "RequestId": request_id,
            "ImageUrl": image_url,
            "CheckerVersion": checker_version,
        })
        task_id = str(result.get("TaskId") or "")
        if not task_id:
            raise TencentAvatarError("invalid_response", "腾讯云人脸检测没有返回任务 ID。")
        return task_id

    def get_face_detection(self, task_id: str) -> dict[str, Any]:
        return self._api_call(self._FACE_STATUS, {"TaskId": task_id})

    def start_photo_customization(self, *, image_url: str, anchor_name: str, sex_type: str, photo_version: int) -> str:
        result = self._api_call(self._MAKE, {
            "AnchorName": self._safe_anchor_name(anchor_name),
            "MakeType": "IMAGE_PHOTO",
            "MaterialCosUrl": image_url,
            "SexType": sex_type,
            "PhotoVersion": photo_version,
            "Notes": "言语康复智能体用户授权照片定制",
        })
        task_id = str(result.get("TaskId") or "")
        if not task_id:
            raise TencentAvatarError("invalid_response", "腾讯云照片数字人定制没有返回任务 ID。")
        return task_id

    def get_customization_progress(self, task_id: str) -> dict[str, Any]:
        return self._api_call(self._MAKE_STATUS, {"TaskId": task_id})

    def _api_call(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid4().hex
        payload = {"Header": {}, "Payload": {"ReqId": request_id, **body}}
        try:
            response = requests.post(
                self._signed_url(endpoint, {"ReqId": request_id}),
                json=payload,
                headers={"Content-Type": "application/json;charset=utf-8"},
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            result = _decode_response(response)
        except (requests.RequestException, ValueError) as exc:
            raise TencentAvatarError("request_failed", f"腾讯云照片数字人接口请求失败：{exc}") from exc
        header = result.get("Header") or {}
        if int(header.get("Code", -1)) != 0:
            raise TencentAvatarError(
                str(header.get("Code", "api_error")),
                _api_error_message(header, "腾讯云照片数字人接口返回失败。"),
            )
        return result.get("Payload") or {}

    def _signed_url(self, endpoint: str, parameters: dict[str, str]) -> str:
        signed = {**parameters, "timestamp": str(int(time.time())), "appkey": self.app_key}
        content = "&".join(f"{key}={value}" for key, value in sorted(signed.items()))
        digest = hmac.new(self.access_token.encode(), content.encode(), hashlib.sha256).digest()
        signature = quote(base64.b64encode(digest).decode())
        query = "&".join(f"{key}={value}" for key, value in signed.items())
        return f"{self.base_url}{endpoint}?{query}&signature={signature}"

    @staticmethod
    def _safe_anchor_name(value: str) -> str:
        cleaned = re.sub(r"[^\w-]", "_", value, flags=re.UNICODE).strip("_")
        if len(cleaned) < 2:
            cleaned = f"陪伴者_{cleaned or '照片'}"
        return cleaned[:50]

    @staticmethod
    def _new_photo_filename() -> str:
        # Tencent validates the final filename separately from the COS path:
        # 2-20 characters, using only letters, numbers, underscores or hyphens.
        # Keep the extension inside that 20-character limit.
        return f"p_{uuid4().hex[:12]}.jpg"

    @staticmethod
    def _prepare_photo(source_path: str, crop: dict[str, object] | None) -> BytesIO:
        try:
            from PIL import Image, ImageOps

            with Image.open(Path(source_path)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                if crop:
                    width, height = image.size
                    left = max(0, min(width - 1, round(float(crop.get("x", 0)) * width)))
                    top = max(0, min(height - 1, round(float(crop.get("y", 0)) * height)))
                    right = max(left + 1, min(width, round((float(crop.get("x", 0)) + float(crop.get("width", 1))) * width)))
                    bottom = max(top + 1, min(height, round((float(crop.get("y", 0)) + float(crop.get("height", 1))) * height)))
                    image = image.crop((left, top, right, bottom))
                if image.width != image.height:
                    edge = min(image.width, image.height)
                    left = (image.width - edge) // 2
                    top = (image.height - edge) // 2
                    image = image.crop((left, top, left + edge, top + edge))
                # Tencent's photo-avatar face detector rejects a face bounding
                # box larger than 700 px. A fixed 640 px square keeps even a
                # tightly framed portrait below that limit while remaining
                # large enough for IMAGE_PHOTO training.
                image = image.resize((640, 640), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="JPEG", quality=92, optimize=True)
                output.seek(0)
                return output
        except (OSError, ValueError, TypeError) as exc:
            raise TencentAvatarError("invalid_photo", "照片无法处理，请重新上传清晰的 JPG、PNG 或 WebP 图片。") from exc


def register_runtime(lease_id: str, runtime: "TencentAvatarRuntime") -> None:
    with _runtimes_lock:
        old = _runtimes.pop(lease_id, None)
        _runtimes[lease_id] = runtime
    if old:
        old.close(close_cloud=True)


def drive_audio(lease_id: str, pcm_data: bytes) -> dict[str, object]:
    with _runtimes_lock:
        runtime = _runtimes.get(lease_id)
    if not runtime:
        raise TencentAvatarError("runtime_missing", "腾讯云数字人连接已失效，请刷新页面后重试。")
    duration_seconds = runtime.send_audio(pcm_data)
    return {"sent_bytes": len(pcm_data), "duration_seconds": duration_seconds}


def drive_text(lease_id: str, text: str) -> dict[str, object]:
    with _runtimes_lock:
        runtime = _runtimes.get(lease_id)
    if not runtime:
        raise TencentAvatarError("runtime_missing", "腾讯云数字人连接已失效，请刷新页面后重试。")
    duration_seconds = runtime.send_text(text)
    return {"accepted": True, "duration_seconds": duration_seconds}


def close_runtime(lease_id: str, provider_session_id: str | None = None) -> None:
    with _runtimes_lock:
        runtime = _runtimes.pop(lease_id, None)
    if runtime:
        runtime.close(close_cloud=True)
    elif provider_session_id and is_configured():
        _close_cloud_session(provider_session_id)


def close_all_runtimes() -> None:
    with _runtimes_lock:
        active = list(_runtimes.values())
        _runtimes.clear()
    for runtime in active:
        runtime.close(close_cloud=True)


class TencentAvatarRuntime:
    _CREATE = "/v2/ivh/sessionmanager/sessionmanagerservice/createsessionbyasset"
    _STATUS = "/v2/ivh/sessionmanager/sessionmanagerservice/statsession"
    _START = "/v2/ivh/sessionmanager/sessionmanagerservice/startsession"
    _CLOSE = "/v2/ivh/sessionmanager/sessionmanagerservice/closesession"
    _COMMAND = "/v2/ws/ivh/interactdriver/interactdriverservice/commandchannel"

    def __init__(self, *, app_key: str, access_token: str, asset_virtualman_key: str, user_id: str,
                 protocol: str, driver_type: int, base_url: str, request_timeout: int, ready_timeout: int,
                 timbre_key: str | None = None) -> None:
        self.app_key = app_key
        self.access_token = access_token
        self.asset_virtualman_key = asset_virtualman_key
        self.user_id = user_id
        self.protocol = protocol
        self.driver_type = driver_type
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.ready_timeout = ready_timeout
        self.timbre_key = timbre_key
        self.session_id: str | None = None
        self.play_stream_addr: str | None = None
        self.ws: websocket.WebSocketApp | None = None
        self._connected = threading.Event()
        self._stopped = threading.Event()
        self._send_lock = threading.Lock()
        self._drive_lock = threading.Lock()
        self._ws_error: str | None = None

    def open(self) -> TencentAvatarSessionResult:
        create_payload: dict[str, Any] = {
            "AssetVirtualmanKey": self.asset_virtualman_key,
            "DriverType": self.driver_type,
            "UserId": self.user_id,
            "Protocol": self.protocol,
            "ExtraInfo": {"AlphaChannelEnable": False},
            "AnchorParam": {"SilenceActionDisabled": False},
        }
        if self.timbre_key:
            create_payload["SpeechParam"] = {
                "TimbreKey": self.timbre_key,
                "Speed": 0.9,
                "Volume": 0,
            }
        created = self._api_call(self._CREATE, create_payload)
        self.session_id = str(created.get("SessionId") or "")
        self.play_stream_addr = str(created.get("PlayStreamAddr") or "")
        if not self.session_id or not self.play_stream_addr:
            raise TencentAvatarError("invalid_response", "腾讯云建流成功，但未返回会话或播放地址。")

        deadline = time.monotonic() + self.ready_timeout
        session_status = int(created.get("SessionStatus", 0))
        while session_status != 1:
            if session_status not in {0, 3}:
                raise TencentAvatarError("session_not_ready", f"腾讯云数字人会话状态异常：{session_status}。")
            if time.monotonic() >= deadline:
                raise TencentAvatarError("ready_timeout", "腾讯云数字人形象加载超时，请稍后重试。")
            time.sleep(2)
            status_payload = self._api_call(self._STATUS, {"SessionId": self.session_id})
            session_status = int(status_payload.get("SessionStatus", 0))

        self._api_call(self._START, {"SessionId": self.session_id})
        self._open_websocket()
        return TencentAvatarSessionResult(self.session_id, self.play_stream_addr, self.protocol)

    def send_audio(self, pcm_data: bytes) -> float:
        if not pcm_data:
            raise TencentAvatarError("empty_audio", "没有可发送的数字人驱动音频。")
        if len(pcm_data) % 2:
            raise TencentAvatarError("invalid_audio", "数字人驱动音频必须是 16 位 PCM。")
        if len(pcm_data) > 10 * 1024 * 1024:
            raise TencentAvatarError("audio_too_large", "单次数字人驱动音频不能超过 10 MB。")
        if not self.session_id or not self._connected.is_set() or self._stopped.is_set():
            raise TencentAvatarError("websocket_closed", "腾讯云数字人连接已断开，请刷新页面后重试。")

        with self._drive_lock:
            request_id = uuid4().hex
            chunk_size = 5120
            chunks = [pcm_data[index:index + chunk_size] for index in range(0, len(pcm_data), chunk_size)]
            for sequence, chunk in enumerate(chunks, start=1):
                self._send_command("SEND_AUDIO", {
                    "Audio": base64.b64encode(chunk).decode("ascii"),
                    "Seq": sequence,
                    "IsFinal": False,
                }, request_id=request_id)
                if sequence < min(6, len(chunks)):
                    time.sleep(0.001)
                elif sequence >= 6 and sequence < len(chunks):
                    time.sleep(0.12)
            self._send_command("SEND_AUDIO", {
                "Audio": "", "Seq": len(chunks) + 1, "IsFinal": True,
            }, request_id=request_id)
        return len(pcm_data) / 32000.0

    def send_text(self, text: str) -> float:
        clean_text = text.strip()
        if not clean_text:
            raise TencentAvatarError("empty_text", "数字人口播文本不能为空。")
        if len(clean_text) > 150:
            raise TencentAvatarError("text_too_long", "数字人口播文本不能超过 150 个字符。")
        if not self.session_id or not self._connected.is_set() or self._stopped.is_set():
            raise TencentAvatarError("websocket_closed", "腾讯云数字人连接已断开，请刷新页面后重试。")
        with self._drive_lock:
            self._send_command("SEND_TEXT", {
                "Text": clean_text,
                "ChatCommand": "NotUseChat",
            })
        # The cloud-rendering command channel does not synchronously return the
        # final audio duration. Keep the patient recorder disabled for a safe,
        # conservative estimate while the WebRTC stream finishes speaking.
        return min(max(len(clean_text) * 0.32 + 0.8, 1.8), 18.0)

    def close(self, *, close_cloud: bool) -> None:
        already_stopped = self._stopped.is_set()
        self._stopped.set()
        self._connected.clear()
        ws = self.ws
        self.ws = None
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if close_cloud and self.session_id and not already_stopped:
            try:
                self._api_call(self._CLOSE, {"SessionId": self.session_id})
            except TencentAvatarError:
                pass

    def _open_websocket(self) -> None:
        if not self.session_id:
            raise TencentAvatarError("missing_session", "腾讯云数字人会话不存在。")
        url = self._signed_url(self._COMMAND, {"requestid": self.session_id}).replace("https://", "wss://", 1)

        def on_open(_ws: websocket.WebSocketApp) -> None:
            self._connected.set()

        def on_error(_ws: websocket.WebSocketApp, error: object) -> None:
            self._ws_error = str(error)

        def on_close(_ws: websocket.WebSocketApp, _code: object, _message: object) -> None:
            self._connected.clear()

        self.ws = websocket.WebSocketApp(url, on_open=on_open, on_error=on_error, on_close=on_close)
        threading.Thread(
            target=self.ws.run_forever,
            kwargs={"ping_interval": 20, "ping_timeout": 10},
            name=f"tencent-avatar-ws-{self.session_id[-6:]}",
            daemon=True,
        ).start()
        if not self._connected.wait(timeout=10):
            raise TencentAvatarError("websocket_timeout", self._ws_error or "腾讯云数字人驱动通道连接超时。")
        threading.Thread(target=self._heartbeat_loop, name="tencent-avatar-heartbeat", daemon=True).start()

    def _heartbeat_loop(self) -> None:
        while not self._stopped.wait(45):
            try:
                self._send_command("SEND_HEARTBEAT", {"Text": "PING"})
            except TencentAvatarError:
                return

    def _send_command(self, command: str, data: dict[str, Any], *, request_id: str | None = None) -> None:
        ws = self.ws
        if not ws or not self._connected.is_set() or not self.session_id:
            raise TencentAvatarError("websocket_closed", "腾讯云数字人驱动通道未连接。")
        payload = {"Header": {}, "Payload": {
            "ReqId": request_id or uuid4().hex,
            "SessionId": self.session_id,
            "Command": command,
            "Data": data,
        }}
        with self._send_lock:
            try:
                ws.send(json.dumps(payload, ensure_ascii=False))
            except Exception as exc:
                self._connected.clear()
                raise TencentAvatarError("websocket_send_failed", f"腾讯云数字人音频发送失败：{exc}") from exc

    def _api_call(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid4().hex
        payload = {"Header": {}, "Payload": {"ReqId": request_id, **body}}
        try:
            response = requests.post(
                self._signed_url(endpoint, {"ReqId": request_id}),
                json=payload,
                headers={"Content-Type": "application/json;charset=utf-8"},
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            result = _decode_response(response)
        except (requests.RequestException, ValueError) as exc:
            raise TencentAvatarError("request_failed", f"腾讯云数字人接口请求失败：{exc}") from exc
        header = result.get("Header") or {}
        if int(header.get("Code", -1)) != 0:
            raise TencentAvatarError(
                str(header.get("Code", "api_error")),
                _api_error_message(header, "腾讯云数字人接口返回失败。"),
            )
        return result.get("Payload") or {}

    def _signed_url(self, endpoint: str, parameters: dict[str, str]) -> str:
        signed = {**parameters, "timestamp": str(int(time.time())), "appkey": self.app_key}
        content = "&".join(f"{key}={value}" for key, value in sorted(signed.items()))
        digest = hmac.new(self.access_token.encode(), content.encode(), hashlib.sha256).digest()
        signature = quote(base64.b64encode(digest).decode())
        query = "&".join(f"{key}={value}" for key, value in signed.items())
        return f"{self.base_url}{endpoint}?{query}&signature={signature}"


def _close_cloud_session(provider_session_id: str) -> None:
    settings = get_settings()
    runtime = TencentAvatarRuntime(
        app_key=settings.tencent_avatar_app_key or "",
        access_token=settings.tencent_avatar_access_token or "",
        asset_virtualman_key=settings.tencent_avatar_asset_virtualman_key or "",
        user_id="cleanup",
        protocol=settings.tencent_avatar_protocol,
        driver_type=settings.tencent_avatar_driver_type,
        base_url=settings.tencent_avatar_api_base_url,
        request_timeout=settings.tencent_avatar_request_timeout_seconds,
        ready_timeout=settings.tencent_avatar_ready_timeout_seconds,
        timbre_key=None,
    )
    runtime.session_id = provider_session_id
    runtime.close(close_cloud=True)
