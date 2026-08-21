import base64
import json
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


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

    def _validate_config(self) -> None:
        missing = []
        if not self.secret_id:
            missing.append("TENCENTCLOUD_SECRET_ID")
        if not self.secret_key:
            missing.append("TENCENTCLOUD_SECRET_KEY")
        if missing:
            raise RuntimeError(f"腾讯云 ASR 配置缺失：{', '.join(missing)}")

    def transcribe(self, audio_path: str) -> str:
        self._validate_config()

        audio_file = Path(audio_path)
        audio_bytes = audio_file.read_bytes()
        if len(audio_bytes) > self.max_sentence_audio_bytes:
            raise RuntimeError("腾讯云一句话识别仅适合 60 秒以内、3MB 以内音频，请缩短训练录音或改用录音文件识别。")

        try:
            from tencentcloud.asr.v20190614 import asr_client, models
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
        except ImportError as exc:
            raise RuntimeError("缺少腾讯云 ASR SDK，请先在 backend 环境安装 requirements.txt。") from exc

        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "asr.tencentcloudapi.com"
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
                    "VoiceFormat": self.voice_format,
                    "UsrAudioKey": f"training-{uuid4()}",
                    "Data": base64.b64encode(audio_bytes).decode("utf-8"),
                    "DataLen": len(audio_bytes),
                }
            )
        )
        response = client.SentenceRecognition(request)
        result = getattr(response, "Result", "") or ""
        if not result.strip():
            raise RuntimeError("腾讯云 ASR 未返回有效转写文本。")
        return result.strip()


def get_asr_provider() -> ASRProvider:
    settings = get_settings()
    if settings.asr_provider == "tencent":
        return TencentASRProvider()
    return MockASRProvider(requested_provider=settings.asr_provider)
