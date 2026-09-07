import unittest
from unittest.mock import patch

from app.core.redaction import REDACTED, provider_error_summary, redact_sensitive_text
from app.integrations.asr import provider as asr_provider


class ErrorRedactionTest(unittest.TestCase):
    def test_redacts_common_secret_shapes(self) -> None:
        text = (
            "request failed api_key=sk-1234567890abcdef token: abc.def.ghi "
            "Authorization: Bearer secret-token-value SecretKey=AKID1234567890abcdef"
        )

        redacted = redact_sensitive_text(text)

        self.assertIn(REDACTED, redacted)
        self.assertNotIn("sk-1234567890abcdef", redacted)
        self.assertNotIn("abc.def.ghi", redacted)
        self.assertNotIn("secret-token-value", redacted)
        self.assertNotIn("AKID1234567890abcdef", redacted)

    def test_provider_summary_is_truncated(self) -> None:
        summary = provider_error_summary("外部服务调用失败", RuntimeError("x" * 500))

        self.assertLessEqual(len(summary), 260)
        self.assertTrue(summary.endswith("..."))

    def test_asr_unknown_error_uses_sanitized_message(self) -> None:
        class BrokenProvider(asr_provider.ASRProvider):
            provider_name = "broken"

            def transcribe(self, audio_path: str) -> str:
                raise RuntimeError("provider crashed token=abc.def.ghi")

        with patch.object(asr_provider, "get_asr_provider", return_value=BrokenProvider()):
            result = asr_provider.transcribe_with_fallback("unused.wav")

        self.assertEqual(result.error_code, "unknown_error")
        self.assertIn(REDACTED, result.error_message or "")
        self.assertNotIn("abc.def.ghi", result.error_message or "")


if __name__ == "__main__":
    unittest.main()
