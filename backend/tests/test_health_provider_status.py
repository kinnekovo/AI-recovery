import unittest
from types import SimpleNamespace

from app.modules.health.router import provider_statuses


class HealthProviderStatusTest(unittest.TestCase):
    def test_mock_providers_are_ready_without_credentials(self) -> None:
        settings = SimpleNamespace(
            speech_eval_provider="mock",
            asr_provider="mock",
            acoustic_provider="mock",
            tts_provider="mock",
            llm_feedback_provider="mock",
        )

        statuses = provider_statuses(settings)

        self.assertTrue(all(item["ready"] for item in statuses.values()))
        self.assertEqual(statuses["asr"]["mode"], "mock")
        self.assertEqual(statuses["tts"]["status"], "ok")

    def test_external_provider_reports_missing_env_names_only(self) -> None:
        settings = SimpleNamespace(
            speech_eval_provider="mock",
            asr_provider="tencent",
            tencentcloud_secret_id="",
            tencentcloud_secret_key="super-secret-value",
            acoustic_provider="mock",
            tts_provider="external",
            tts_api_key="",
            tts_base_url="https://tts.example",
            llm_feedback_provider="external",
            llm_feedback_api_key="sk-secret-value",
            llm_feedback_base_url="",
        )

        statuses = provider_statuses(settings)

        self.assertFalse(statuses["asr"]["ready"])
        self.assertEqual(statuses["asr"]["missing_env"], ["TENCENTCLOUD_SECRET_ID"])
        self.assertEqual(statuses["tts"]["missing_env"], ["TTS_API_KEY"])
        self.assertEqual(statuses["llm_feedback"]["missing_env"], ["LLM_FEEDBACK_BASE_URL"])
        self.assertNotIn("super-secret-value", str(statuses))
        self.assertNotIn("sk-secret-value", str(statuses))


if __name__ == "__main__":
    unittest.main()
