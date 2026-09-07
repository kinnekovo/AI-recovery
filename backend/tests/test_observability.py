import json
import tempfile
import unittest
from unittest.mock import patch

from app.core.observability import APP_LOGGER_NAME, log_event
from app.integrations.asr import provider as asr_provider


class ObservabilityTest(unittest.TestCase):
    def test_log_event_outputs_structured_redacted_json(self) -> None:
        with self.assertLogs(APP_LOGGER_NAME, level="WARNING") as captured:
            log_event(
                "warning",
                "provider",
                "external_failure",
                error_message="request failed Authorization: Bearer secret-token",
            )

        message = captured.output[0].split(":", 2)[-1]
        payload = json.loads(message)
        self.assertEqual(payload["category"], "provider")
        self.assertEqual(payload["event"], "external_failure")
        self.assertNotIn("secret-token", message)

    def test_asr_fallback_writes_provider_log(self) -> None:
        class BrokenProvider(asr_provider.ASRProvider):
            provider_name = "broken"

            def transcribe(self, audio_path: str) -> str:
                raise asr_provider.ASRProviderError("provider_error", "failed token=abc.def.ghi")

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch.object(asr_provider, "get_asr_provider", return_value=BrokenProvider()):
                with self.assertLogs(APP_LOGGER_NAME, level="WARNING") as captured:
                    result = asr_provider.transcribe_with_fallback(audio.name)

        self.assertTrue(result.fallback_used)
        self.assertIn("asr_fallback", captured.output[0])
        self.assertNotIn("abc.def.ghi", captured.output[0])


if __name__ == "__main__":
    unittest.main()
