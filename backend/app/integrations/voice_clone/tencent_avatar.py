from __future__ import annotations

from pathlib import Path

from app.integrations.tencent_avatar.provider import TencentAvatarCustomizationClient, TencentAvatarError
from app.integrations.voice_clone.provider import (
    VoiceCloneProvider,
    VoiceCloneProviderError,
    VoiceCloneTask,
    VoiceCloneTaskStatus,
    VoiceTrainingText,
)


SUPPORTED_IVH_CODECS = {"wav", "mp3", "aac", "m4a", "wma", "asf"}
MAX_IVH_AUDIO_BYTES = 20 * 1024 * 1024


class TencentAvatarVoiceCloneProvider(VoiceCloneProvider):
    """Tencent Digital Human ZERO_SHOT_VOICE two-stage adapter."""

    name = "tencent_avatar"

    def __init__(self) -> None:
        self.client = TencentAvatarCustomizationClient()

    def get_training_text(self) -> VoiceTrainingText:
        try:
            payload = self.client.get_voice_training_text()
            texts = payload.get("Texts") or []
            item = next((value for value in texts if isinstance(value, dict)), None)
            if not item or not item.get("TextId") or not item.get("Text"):
                raise VoiceCloneProviderError("empty_training_text", "腾讯云未返回可用的声音复刻朗读文本。")
            return VoiceTrainingText(text_id=str(item["TextId"]), text=str(item["Text"]))
        except VoiceCloneProviderError:
            raise
        except TencentAvatarError as exc:
            raise self._to_error(exc) from exc

    def create_one_sentence_clone(
        self, audio_path: str, *, text_id: str | None, voice_name: str, voice_gender: int
    ) -> VoiceCloneTask:
        path = Path(audio_path)
        codec = path.suffix.lower().lstrip(".")
        if codec not in SUPPORTED_IVH_CODECS:
            raise VoiceCloneProviderError("unsupported_audio", "声音复刻仅支持 WAV、MP3、AAC、M4A、WMA 或 ASF 音频。")
        if not path.is_file() or path.stat().st_size == 0:
            raise VoiceCloneProviderError("empty_audio", "声音样本文件为空或无法读取。")
        if path.stat().st_size > MAX_IVH_AUDIO_BYTES:
            raise VoiceCloneProviderError("audio_too_large", "声音复刻录音不能超过 20MB。")
        try:
            audio_url = self.client.upload_voice_sample(str(path), codec)
            task_id = self.client.start_voice_quality_detection(audio_url, text_id=text_id)
            return VoiceCloneTask(task_id=f"detect:{task_id}")
        except TencentAvatarError as exc:
            raise self._to_error(exc) from exc

    def get_task_status(
        self, task_id: str, *, voice_name: str = "陪伴声音", voice_gender: int = 2
    ) -> VoiceCloneTaskStatus:
        try:
            if task_id.startswith("detect:"):
                provider_task_id = task_id.split(":", 1)[1]
                payload = self.client.get_voice_quality_detection(provider_task_id)
                state = str(payload.get("TaskState") or "PROCESSING").upper()
                if state == "PROCESSING":
                    return VoiceCloneTaskStatus(task_id, "detecting", 1, stage="QUALITY_CHECK")
                detection_code = int(payload.get("DetectionCode", -1))
                audio_id = str(payload.get("AudioId") or "")
                if state != "SUCCESS" or detection_code != 0 or not audio_id:
                    message = str(payload.get("DetectionMsg") or "录音未通过腾讯云音质检测，请按指定文本重新录制。")
                    return VoiceCloneTaskStatus(task_id, "failed", 3, error_message=message)
                make_id = self.client.start_voice_customization(
                    audio_id=audio_id,
                    anchor_name=f"{voice_name}_{provider_task_id[-8:]}",
                    sex_type="MALE" if voice_gender == 1 else "FEMALE",
                )
                return VoiceCloneTaskStatus(
                    task_id,
                    "training",
                    1,
                    stage="TRAIN",
                    next_task_id=f"make:{make_id}",
                )

            provider_task_id = task_id.split(":", 1)[1] if task_id.startswith("make:") else task_id
            payload = self.client.get_customization_progress(provider_task_id)
            state = str(payload.get("Status") or "MAKING").upper()
            if state == "MAKING":
                stage = str(payload.get("StageV2") or payload.get("StatusV2") or "TRAIN")
                return VoiceCloneTaskStatus(task_id, "training", 1, stage=stage)
            if state != "SUCCESS":
                return VoiceCloneTaskStatus(
                    task_id,
                    "failed",
                    3,
                    error_message=str(payload.get("FailMessage") or "腾讯云声音复刻失败，请重新录制。"),
                )
            assets = payload.get("AssetList") or []
            asset = next((item for item in assets if isinstance(item, dict) and item.get("TimbreKey")), None)
            if not asset:
                return VoiceCloneTaskStatus(task_id, "failed", 3, error_message="任务完成但未返回专属音色。")
            sample_url = str(asset.get("TimbreSample") or "") or None
            return VoiceCloneTaskStatus(
                task_id,
                "success",
                2,
                fast_voice_type=str(asset["TimbreKey"]),
                sample_url=sample_url,
                stage="END",
            )
        except TencentAvatarError as exc:
            raise self._to_error(exc) from exc

    @staticmethod
    def _to_error(exc: TencentAvatarError) -> VoiceCloneProviderError:
        quota_markers = (
            "LimitExceeded",
            "超过配额限制",
            "无可用定制资产",
            "UnauthorizedOperation",
        )
        if any(marker in exc.code or marker in exc.message for marker in quota_markers):
            return VoiceCloneProviderError(
                "quota_exhausted",
                "当前腾讯云账号没有可用的“声音复刻-极速版”定制配额。"
                "数字人交互并发不包含声音复刻配额，请购买声音复刻配额后重试。",
            )
        return VoiceCloneProviderError(exc.code, exc.message)
