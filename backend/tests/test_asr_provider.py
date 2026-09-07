import os
import tempfile
import unittest

from app.core.config import get_settings
from app.integrations.asr.provider import transcribe_with_fallback


class ASRProviderFallbackTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ("ASR_PROVIDER", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_tencent_config_error_falls_back_to_mock_with_error_code(self) -> None:
        os.environ["ASR_PROVIDER"] = "tencent"
        os.environ["TENCENTCLOUD_SECRET_ID"] = ""
        os.environ["TENCENTCLOUD_SECRET_KEY"] = ""
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(b"fake-audio")
            audio.flush()
            result = transcribe_with_fallback(audio.name)

        self.assertEqual(result.text, "这是一次模拟转写结果")
        self.assertEqual(result.provider_name, "mock")
        self.assertEqual(result.requested_provider, "tencent")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.error_code, "config_missing")
        self.assertIn("TENCENTCLOUD_SECRET_ID", result.error_message or "")

    def test_unknown_provider_uses_mock_without_error(self) -> None:
        os.environ["ASR_PROVIDER"] = "not-real"
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            result = transcribe_with_fallback(audio.name)

        self.assertEqual(result.provider_name, "mock")
        self.assertEqual(result.requested_provider, "not-real")
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.error_code)


if __name__ == "__main__":
    unittest.main()
