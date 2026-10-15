import base64
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.redaction import provider_error_summary


ONE_SENTENCE_TASK_TYPE = 5
ONE_SENTENCE_VOICE_TYPE = 200000000
SUPPORTED_CODECS = {"wav", "mp3", "aac", "m4a"}
MAX_AUDIO_BYTES = 2 * 1024 * 1024


class VoiceCloneProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VoiceTrainingText:
    text_id: str
    text: str


@dataclass(frozen=True)
class VoiceCloneTask:
    task_id: str


@dataclass(frozen=True)
class VoiceCloneTaskStatus:
    task_id: str
    status: str
    status_code: int
    fast_voice_type: str | None = None
    error_message: str | None = None
    sample_url: str | None = None
    stage: str | None = None
    next_task_id: str | None = None


class VoiceCloneProvider:
    name = "base"

    def get_training_text(self) -> VoiceTrainingText:
        raise NotImplementedError

    def create_one_sentence_clone(
        self, audio_path: str, *, text_id: str | None, voice_name: str, voice_gender: int
    ) -> VoiceCloneTask:
        raise NotImplementedError

    def get_task_status(self, task_id: str, *, voice_name: str = "陪伴声音", voice_gender: int = 2) -> VoiceCloneTaskStatus:
        raise NotImplementedError


class MockVoiceCloneProvider(VoiceCloneProvider):
    name = "mock"

    def get_training_text(self) -> VoiceTrainingText:
        return VoiceTrainingText(text_id="mock-training-text", text="请清晰朗读：我已确认这是我的声音，仅用于康复训练。")

    def create_one_sentence_clone(
        self, audio_path: str, *, text_id: str | None, voice_name: str, voice_gender: int
    ) -> VoiceCloneTask:
        return VoiceCloneTask(task_id=f"mock-task-{uuid4().hex}")

    def get_task_status(self, task_id: str, *, voice_name: str = "陪伴声音", voice_gender: int = 2) -> VoiceCloneTaskStatus:
        return VoiceCloneTaskStatus(task_id=task_id, status="success", status_code=2, fast_voice_type=f"mock_voice_{task_id[-8:]}")


class TencentVCLProvider(VoiceCloneProvider):
    """Tencent Cloud VCL one-sentence cloning adapter.

    Task creation and polling are intentionally separate. Callers create no more
    than one task per agent, then only poll that stored task ID.
    """

    name = "tencent"

    def __init__(self) -> None:
        settings = get_settings()
        self.secret_id = settings.tencentcloud_secret_id
        self.secret_key = settings.tencentcloud_secret_key
        self.region = settings.tencent_vcl_region
        self.timeout_seconds = settings.vcl_timeout_seconds

    def _client(self):
        if not self.secret_id or not self.secret_key:
            raise VoiceCloneProviderError("config_missing", "腾讯云声音复刻配置缺失：请检查 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY。")
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.vrs.v20200824 import models, vrs_client
        except ImportError as exc:
            raise VoiceCloneProviderError("dependency_missing", "缺少腾讯云声音复刻 SDK，请安装 backend/requirements.txt。") from exc
        http_profile = HttpProfile()
        http_profile.endpoint = "vrs.tencentcloudapi.com"
        http_profile.reqTimeout = self.timeout_seconds
        profile = ClientProfile()
        profile.httpProfile = http_profile
        return vrs_client.VrsClient(credential.Credential(self.secret_id, self.secret_key), self.region, profile), models

    def get_training_text(self) -> VoiceTrainingText:
        client, models = self._client()
        try:
            request = models.GetTrainingTextRequest()
            request.TaskType = ONE_SENTENCE_TASK_TYPE
            request.TextLanguage = 1
            response = client.GetTrainingText(request)
            records = getattr(getattr(response, "Data", None), "TrainingTextList", None) or []
            if not records or not getattr(records[0], "TextId", None) or not getattr(records[0], "Text", None):
                raise VoiceCloneProviderError("empty_training_text", "腾讯云未返回可用的声音复刻朗读文本。")
            return VoiceTrainingText(text_id=records[0].TextId, text=records[0].Text)
        except VoiceCloneProviderError:
            raise
        except Exception as exc:
            raise self._to_error(exc, "获取声音复刻朗读文本失败") from exc

    def create_one_sentence_clone(
        self, audio_path: str, *, text_id: str | None, voice_name: str, voice_gender: int
    ) -> VoiceCloneTask:
        path = Path(audio_path)
        codec = path.suffix.lower().lstrip(".")
        if codec not in SUPPORTED_CODECS:
            raise VoiceCloneProviderError("unsupported_audio", "声音复刻仅支持 WAV、MP3、AAC 或 M4A 音频。")
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise VoiceCloneProviderError("audio_unavailable", "声音样本文件无法读取。") from exc
        if not content:
            raise VoiceCloneProviderError("empty_audio", "声音样本文件为空。")
        if len(content) > MAX_AUDIO_BYTES:
            raise VoiceCloneProviderError("audio_too_large", "一句话声音复刻的音频不能超过 2MB。")

        client, models = self._client()
        try:
            detection = models.DetectEnvAndSoundQualityRequest()
            detection.TextId = text_id
            detection.AudioData = base64.b64encode(content).decode("ascii")
            detection.TypeId = 2
            detection.Codec = codec
            detection.TaskType = ONE_SENTENCE_TASK_TYPE
            response = client.DetectEnvAndSoundQuality(detection)
            data = getattr(response, "Data", None)
            code = getattr(data, "DetectionCode", None)
            audio_id = getattr(data, "AudioId", None)
            message = getattr(data, "DetectionMsg", None) or "音质或朗读文本未通过检测，请按页面文本重新录制。"
            if code != 0 or not audio_id:
                raise VoiceCloneProviderError("quality_rejected", message)

            create = models.CreateVRSTaskRequest()
            create.SessionId = f"rehab-vcl-{uuid4()}"
            create.VoiceName = voice_name[:80]
            create.VoiceGender = voice_gender
            create.VoiceLanguage = 1
            create.AudioIdList = [audio_id]
            create.Codec = codec
            create.TaskType = ONE_SENTENCE_TASK_TYPE
            create.EnableVoiceEnhance = 0
            task_response = client.CreateVRSTask(create)
            task_id = getattr(getattr(task_response, "Data", None), "TaskId", None)
            if not task_id:
                raise VoiceCloneProviderError("empty_task", "腾讯云未返回声音复刻任务 ID。")
            return VoiceCloneTask(task_id=task_id)
        except VoiceCloneProviderError:
            raise
        except Exception as exc:
            raise self._to_error(exc, "声音复刻检测或任务创建失败") from exc

    def get_task_status(self, task_id: str, *, voice_name: str = "陪伴声音", voice_gender: int = 2) -> VoiceCloneTaskStatus:
        client, models = self._client()
        try:
            request = models.DescribeVRSTaskStatusRequest()
            request.TaskId = task_id
            response = client.DescribeVRSTaskStatus(request)
            data = getattr(response, "Data", None)
            return VoiceCloneTaskStatus(
                task_id=task_id,
                status=str(getattr(data, "StatusStr", "unknown")),
                status_code=int(getattr(data, "Status", -1)),
                fast_voice_type=getattr(data, "FastVoiceType", None) or None,
                error_message=getattr(data, "ErrorMsg", None) or None,
            )
        except Exception as exc:
            raise self._to_error(exc, "查询声音复刻任务状态失败") from exc

    @staticmethod
    def _to_error(exc: Exception, prefix: str) -> VoiceCloneProviderError:
        detail = str(exc)
        if "PkgExhausted" in detail or "resource pack allowance has been exhausted" in detail:
            return VoiceCloneProviderError("quota_exhausted", "腾讯云声音复刻资源包额度已用尽，请补充资源包后重试。")
        if "AuthFailure" in detail or "UnauthorizedOperation" in detail:
            return VoiceCloneProviderError("credential_invalid", "腾讯云声音复刻凭据无效或未开通 VCL 权限。")
        return VoiceCloneProviderError("provider_error", provider_error_summary(prefix, exc))


def get_voice_clone_provider() -> VoiceCloneProvider:
    provider = get_settings().vcl_provider
    if provider == "mock":
        return MockVoiceCloneProvider()
    if provider in {"tencent", "tencent_avatar"}:
        from app.integrations.voice_clone.tencent_avatar import TencentAvatarVoiceCloneProvider

        return TencentAvatarVoiceCloneProvider()
    raise VoiceCloneProviderError("unknown_provider", f"不支持的 VCL_PROVIDER：{provider}")
