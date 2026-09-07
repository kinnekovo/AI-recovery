import base64
import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

from app.core.config import get_settings
from app.core.observability import log_event
from app.core.redaction import provider_error_summary


@dataclass(frozen=True)
class ASRTranscriptionResult:
    text: str
    provider_name: str
    requested_provider: str
    fallback_used: bool = False
    error_code: str | None = None
    error_message: str | None = None


class ASRProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ASRProvider:
    provider_name = "base"

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError


class MockASRProvider(ASRProvider):
    provider_name = "mock"

    def __init__(self, requested_provider: str = "mock") -> None:
        self.requested_provider = requested_provider

    def transcribe(self, audio_path: str) -> str:
        return "这是一次模拟转写结果"


class TencentASRProvider(ASRProvider):
    provider_name = "tencent"
    max_sentence_audio_bytes = 3 * 1024 * 1024

    def __init__(self) -> None:
        settings = get_settings()
        self.secret_id = settings.tencentcloud_secret_id
        self.secret_key = settings.tencentcloud_secret_key
        self.app_id = settings.tencent_asr_app_id
        self.region = settings.tencent_asr_region
        self.engine_model_type = settings.tencent_asr_engine_model_type
        self.voice_format = settings.tencent_asr_voice_format
        self.ffmpeg_bin = settings.ffmpeg_bin or self._bundled_ffmpeg_bin()

    def _validate_config(self) -> None:
        missing = []
        if not self.secret_id:
            missing.append("TENCENTCLOUD_SECRET_ID")
        if not self.secret_key:
            missing.append("TENCENTCLOUD_SECRET_KEY")
        if missing:
            raise ASRProviderError("config_missing", f"腾讯云 ASR 配置缺失：{', '.join(missing)}")

    def transcribe(self, audio_path: str) -> str:
        self._validate_config()
        prepared_audio: Path | None = None
        try:
            prepared_audio, voice_format = self._prepare_audio(audio_path)
            audio_bytes = prepared_audio.read_bytes()
            if len(audio_bytes) > self.max_sentence_audio_bytes:
                raise ASRProviderError("payload_too_large", "腾讯云一句话识别仅适合 60 秒以内、3MB 以内音频，请缩短训练录音或改用录音文件识别。")

            try:
                from tencentcloud.asr.v20190614 import asr_client, models
                from tencentcloud.common import credential
                from tencentcloud.common.profile.client_profile import ClientProfile
                from tencentcloud.common.profile.http_profile import HttpProfile
            except ImportError as exc:
                raise ASRProviderError("dependency_missing", "缺少腾讯云 ASR SDK，请先在 backend 环境安装 requirements.txt。") from exc

            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "asr.tencentcloudapi.com"
            http_profile.reqTimeout = get_settings().asr_timeout_seconds
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            client = asr_client.AsrClient(cred, self.region, client_profile)

            request = models.SentenceRecognitionRequest()
            request.from_json_string(
                json.dumps(
                    {
                        "ProjectId": 0,
                        "SubServiceType": 2,
                        "EngSerViceType": self.engine_model_type,
                        "SourceType": 1,
                        "VoiceFormat": voice_format,
                        "UsrAudioKey": f"training-{uuid4()}",
                        "Data": base64.b64encode(audio_bytes).decode("utf-8"),
                        "DataLen": len(audio_bytes),
                    }
                )
            )
            try:
                response = client.SentenceRecognition(request)
            except Exception as exc:
                raise ASRProviderError("provider_error", provider_error_summary("腾讯云 ASR 调用失败", exc)) from exc
            result = getattr(response, "Result", "") or ""
            if not result.strip():
                raise ASRProviderError("empty_result", "腾讯云 ASR 未返回有效转写文本。")
            return result.strip()
        finally:
            if prepared_audio is not None:
                prepared_audio.unlink(missing_ok=True)

    def _prepare_audio(self, audio_path: str) -> tuple[Path, str]:
        if not self.ffmpeg_bin:
            raise ASRProviderError("transcode_dependency_missing", "未找到 ffmpeg，无法将浏览器录音转换为腾讯 ASR 支持的 WAV 格式。")

        source = Path(audio_path)
        if not source.is_file():
            raise ASRProviderError("audio_missing", "待识别的录音文件不存在。")

        with tempfile.NamedTemporaryFile(prefix="tencent-asr-", suffix=".wav", delete=False) as temp_file:
            destination = Path(temp_file.name)
        command = [
            self.ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
            if destination.stat().st_size == 0:
                raise RuntimeError("转换后的音频为空")
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            destination.unlink(missing_ok=True)
            raise ASRProviderError("audio_transcode_failed", "录音格式转换失败，请重新录制后再试。") from exc
        return destination, "wav"

    @staticmethod
    def _bundled_ffmpeg_bin() -> str | None:
        try:
            import imageio_ffmpeg
        except ImportError:
            return None
        return imageio_ffmpeg.get_ffmpeg_exe()


def get_asr_provider() -> ASRProvider:
    settings = get_settings()
    if settings.asr_provider == "tencent":
        return TencentASRProvider()
    return MockASRProvider(requested_provider=settings.asr_provider)


def transcribe_with_fallback(audio_path: str) -> ASRTranscriptionResult:
    provider = get_asr_provider()
    requested_provider = getattr(provider, "requested_provider", provider.provider_name)
    try:
        text = provider.transcribe(audio_path)
        return ASRTranscriptionResult(
            text=text,
            provider_name=provider.provider_name,
            requested_provider=requested_provider,
        )
    except ASRProviderError as exc:
        if requested_provider == "tencent":
            log_event(
                "error",
                "provider",
                "asr_failed",
                requested_provider=requested_provider,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        log_event(
            "warning",
            "provider",
            "asr_fallback",
            requested_provider=requested_provider,
            fallback_provider="mock",
            error_code=exc.code,
            error_message=exc.message,
        )
        fallback = MockASRProvider(requested_provider=requested_provider)
        return ASRTranscriptionResult(
            text=fallback.transcribe(audio_path),
            provider_name=fallback.provider_name,
            requested_provider=requested_provider,
            fallback_used=True,
            error_code=exc.code,
            error_message=exc.message,
        )
    except Exception as exc:
        error_message = provider_error_summary("ASR 调用失败", exc)
        log_event(
            "error",
            "provider",
            "asr_unexpected_error",
            requested_provider=requested_provider,
            fallback_provider="mock",
            error_code="unknown_error",
            error_message=error_message,
        )
        fallback = MockASRProvider(requested_provider=requested_provider)
        return ASRTranscriptionResult(
            text=fallback.transcribe(audio_path),
            provider_name=fallback.provider_name,
            requested_provider=requested_provider,
            fallback_used=True,
            error_code="unknown_error",
            error_message=error_message,
        )
