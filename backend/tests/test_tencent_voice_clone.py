import unittest

from app.integrations.tencent_avatar.provider import TencentAvatarError
from app.integrations.voice_clone.tencent_avatar import TencentAvatarVoiceCloneProvider


class FakeTencentAvatarClient:
    def __init__(self, *, detect=None, progress=None) -> None:
        self.detect = detect or {}
        self.progress = progress or {}
        self.make_calls: list[dict[str, object]] = []

    def get_voice_quality_detection(self, task_id: str):
        return self.detect

    def start_voice_customization(self, **kwargs):
        self.make_calls.append(kwargs)
        return "make-task-id"

    def get_customization_progress(self, task_id: str):
        return self.progress


class TencentAvatarVoiceCloneTest(unittest.TestCase):
    def provider_with(self, client: FakeTencentAvatarClient) -> TencentAvatarVoiceCloneProvider:
        provider = TencentAvatarVoiceCloneProvider.__new__(TencentAvatarVoiceCloneProvider)
        provider.client = client
        return provider

    def test_quality_pass_starts_zero_shot_customization(self) -> None:
        client = FakeTencentAvatarClient(detect={
            "TaskState": "SUCCESS",
            "DetectionCode": 0,
            "AudioId": "audio-id",
        })
        result = self.provider_with(client).get_task_status(
            "detect:quality-task", voice_name="妈妈", voice_gender=2
        )

        self.assertEqual(result.status, "training")
        self.assertEqual(result.next_task_id, "make:make-task-id")
        self.assertEqual(client.make_calls[0]["audio_id"], "audio-id")
        self.assertEqual(client.make_calls[0]["sex_type"], "FEMALE")

    def test_completed_customization_returns_timbre_key(self) -> None:
        client = FakeTencentAvatarClient(progress={
            "Status": "SUCCESS",
            "AssetList": [{
                "MakeType": "ZERO_SHOT_VOICE",
                "TimbreKey": "custom-timbre",
                "TimbreSample": "https://example.test/sample.mp3",
            }],
        })
        result = self.provider_with(client).get_task_status("make:voice-task")

        self.assertEqual(result.status_code, 2)
        self.assertEqual(result.fast_voice_type, "custom-timbre")
        self.assertEqual(result.sample_url, "https://example.test/sample.mp3")

    def test_quality_rejection_is_not_submitted_for_customization(self) -> None:
        client = FakeTencentAvatarClient(detect={
            "TaskState": "SUCCESS",
            "DetectionCode": -2,
            "DetectionMsg": "存在错读或漏读",
        })
        result = self.provider_with(client).get_task_status("detect:quality-task")

        self.assertEqual(result.status_code, 3)
        self.assertIn("错读", result.error_message or "")
        self.assertEqual(client.make_calls, [])

    def test_limit_exceeded_is_reported_as_voice_clone_quota(self) -> None:
        error = TencentAvatarVoiceCloneProvider._to_error(
            TencentAvatarError("LimitExceeded", "LimitExceeded:超过配额限制")
        )

        self.assertEqual(error.code, "quota_exhausted")
        self.assertIn("声音复刻-极速版", error.message)
        self.assertIn("交互并发不包含", error.message)


if __name__ == "__main__":
    unittest.main()
