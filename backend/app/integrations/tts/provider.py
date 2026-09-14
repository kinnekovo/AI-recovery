import base64
import json
import math
import os
import subprocess
import wave
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.redaction import provider_error_summary


class TTSProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def tencent_tts_error(exc: Exception) -> TTSProviderError:
    """Convert Tencent SDK failures into a safe, actionable product error."""
    detail = str(exc)
    if "PkgExhausted" in detail or "resource pack allowance has been exhausted" in detail:
        return TTSProviderError(
            "quota_exhausted",
            "腾讯云语音资源包额度已用尽，请补充额度后重试；当前页面会自动改用设备语音。",
        )
    if "AuthFailure" in detail or "UnauthorizedOperation" in detail:
        return TTSProviderError("credential_invalid", "腾讯云 TTS 凭据无效或没有语音合成权限，请检查云端授权。")
    return TTSProviderError("provider_error", provider_error_summary("腾讯云 TTS 调用失败", exc))


class TTSProvider:
    name = "base"

    def synthesize(self, text: str, voice_id: str) -> str:
        raise NotImplementedError

    def cache_identity(self, voice_id: str) -> str:
        return f"{self.name}|{voice_id}"


class MockTTSProvider(TTSProvider):
    name = "mock"

    def synthesize(self, text: str, voice_id: str) -> str:
        output_dir = get_settings().storage_root / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"speech_{uuid4().hex}.wav"
        sample_rate = 16000
        duration_seconds = 1.2
        frames = int(sample_rate * duration_seconds)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for index in range(frames):
                value = int(16000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                wav.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
        return str(path)


class TencentTTSProvider(TTSProvider):
    """Tencent Cloud TextToVoice adapter for short rehabilitation prompts."""

    name = "tencent"
    max_text_length = 150

    def __init__(self) -> None:
        settings = get_settings()
        self.secret_id = settings.tencentcloud_secret_id
        self.secret_key = settings.tencentcloud_secret_key
        self.region = settings.tencent_tts_region
        self.voice_type = settings.tencent_tts_voice_type
        self.sample_rate = settings.tencent_tts_sample_rate
        self.speed = settings.tencent_tts_speed
        self.timeout_seconds = settings.tts_timeout_seconds
        self.storage_root = settings.storage_root

    def _validate_config(self) -> None:
        missing = []
        if not self.secret_id:
            missing.append("TENCENTCLOUD_SECRET_ID")
        if not self.secret_key:
            missing.append("TENCENTCLOUD_SECRET_KEY")
        if missing:
            raise TTSProviderError("config_missing", f"腾讯云 TTS 配置缺失：{', '.join(missing)}")
        if self.sample_rate not in {8000, 16000, 24000}:
            raise TTSProviderError("invalid_sample_rate", "腾讯云 TTS 采样率仅支持 8000、16000 或 24000。")
        if not -2 <= self.speed <= 6:
            raise TTSProviderError("invalid_speed", "腾讯云 TTS 语速必须在 -2 到 6 之间。")

    def cache_identity(self, voice_id: str) -> str:
        selected_voice_type = 200000000 if voice_id.startswith("WCHN-") else self.voice_type
        return f"{self.name}|{voice_id}|{selected_voice_type}|{self.sample_rate}|{self.speed}"

    def synthesize(self, text: str, voice_id: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise TTSProviderError("empty_text", "数字人口播文本不能为空。")
        if len(normalized) > self.max_text_length:
            raise TTSProviderError("text_too_long", "数字人口播文本不能超过 150 个字符。")
        self._validate_config()
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.tts.v20190823 import models, tts_client
        except ImportError as exc:
            raise TTSProviderError("dependency_missing", "缺少腾讯云 TTS SDK，请先在 backend 环境安装 requirements.txt。") from exc

        try:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "tts.tencentcloudapi.com"
            http_profile.reqTimeout = self.timeout_seconds
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            client = tts_client.TtsClient(cred, self.region, client_profile)
            request = models.TextToVoiceRequest()
            payload = {
                "Text": normalized,
                "SessionId": f"rehab-{uuid4()}",
                "VoiceType": 200000000 if voice_id.startswith("WCHN-") else self.voice_type,
                "SampleRate": self.sample_rate,
                "Speed": self.speed,
                "Codec": "wav",
                "PrimaryLanguage": 1,
            }
            if voice_id.startswith("WCHN-"):
                payload["FastVoiceType"] = voice_id
            request.from_json_string(json.dumps(payload))
            response = client.TextToVoice(request)
            audio_base64 = getattr(response, "Audio", "") or ""
            if not audio_base64:
                raise TTSProviderError("empty_result", "腾讯云 TTS 未返回有效音频。")
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except TTSProviderError:
            raise
        except Exception as exc:
            raise tencent_tts_error(exc) from exc

        output_dir = self.storage_root / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"tencent_tts_{uuid4().hex}.wav"
        try:
            path.write_bytes(audio_bytes)
        except OSError as exc:
            raise TTSProviderError("storage_failed", "数字人口播音频保存失败。") from exc
        if path.stat().st_size == 0:
            path.unlink(missing_ok=True)
            raise TTSProviderError("empty_result", "腾讯云 TTS 返回了空音频。")
        return str(path)


class WindowsTTSProvider(TTSProvider):
    """Offline Windows SAPI voice for local demos when cloud TTS is unavailable."""

    name = "windows"
    max_text_length = 150

    def __init__(self) -> None:
        settings = get_settings()
        self.voice = settings.windows_tts_voice
        self.speed = settings.windows_tts_speed
        self.timeout_seconds = settings.tts_timeout_seconds
        self.storage_root = settings.storage_root

    def cache_identity(self, voice_id: str) -> str:
        return f"{self.name}|{self.voice}|{self.speed}"

    def synthesize(self, text: str, voice_id: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise TTSProviderError("empty_text", "数字人口播文本不能为空。")
        if len(normalized) > self.max_text_length:
            raise TTSProviderError("text_too_long", "数字人口播文本不能超过 150 个字符。")
        if os.name != "nt":
            raise TTSProviderError("platform_unsupported", "本地 Windows TTS 仅可在 Windows 上使用。")
        if not -10 <= self.speed <= 10:
            raise TTSProviderError("invalid_speed", "本地语音语速必须在 -10 到 10 之间。")

        output_dir = self.storage_root / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"windows_tts_{uuid4().hex}.wav"
        environment = os.environ.copy()
        environment.update(
            {
                "SPEECH_REHAB_TTS_TEXT": normalized,
                "SPEECH_REHAB_TTS_VOICE": self.voice,
                "SPEECH_REHAB_TTS_SPEED": str(self.speed),
                "SPEECH_REHAB_TTS_OUTPUT": str(path),
            }
        )
        script = """
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $speaker.SelectVoice($env:SPEECH_REHAB_TTS_VOICE)
  $speaker.Rate = [int]$env:SPEECH_REHAB_TTS_SPEED
  $speaker.SetOutputToWaveFile($env:SPEECH_REHAB_TTS_OUTPUT)
  $speaker.Speak($env:SPEECH_REHAB_TTS_TEXT)
} finally {
  $speaker.Dispose()
}
"""
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            path.unlink(missing_ok=True)
            raise TTSProviderError("runtime_unavailable", "本地 Windows 语音无法启动。") from exc
        if result.returncode != 0 or not path.is_file() or path.stat().st_size <= 44:
            path.unlink(missing_ok=True)
            raise TTSProviderError("synthesis_failed", "本地中文语音合成失败，请检查 Windows 中文语音是否已安装。")
        return str(path)


def get_tts_provider() -> TTSProvider:
    provider = get_settings().tts_provider
    if provider == "mock":
        return MockTTSProvider()
    if provider == "tencent":
        return TencentTTSProvider()
    if provider == "windows":
        return WindowsTTSProvider()
    raise TTSProviderError("unknown_provider", f"不支持的 TTS_PROVIDER：{provider}")
