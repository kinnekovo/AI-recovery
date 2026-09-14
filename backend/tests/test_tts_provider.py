import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations.tts.provider import (
    MockTTSProvider,
    TencentTTSProvider,
    TTSProviderError,
    WindowsTTSProvider,
    get_tts_provider,
    tencent_tts_error,
)
from app.modules.training.service import avatar_speech_cache_name


def settings(**overrides):
    values = {
        "tts_provider": "mock",
        "storage_root": Path(tempfile.gettempdir()) / "speech-rehab-tts-tests",
        "tencentcloud_secret_id": "id",
        "tencentcloud_secret_key": "key",
        "tencent_tts_region": "ap-guangzhou",
        "tencent_tts_voice_type": 502001,
        "tencent_tts_sample_rate": 24000,
        "tencent_tts_speed": -1.0,
        "tts_timeout_seconds": 10,
        "windows_tts_voice": "Microsoft Huihui Desktop",
        "windows_tts_speed": -1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TTSProviderTest(unittest.TestCase):
    def test_mock_provider_writes_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.integrations.tts.provider.get_settings", return_value=settings(storage_root=Path(temp_dir))):
                path = Path(MockTTSProvider().synthesize("你好", "default"))
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 44)

    def test_tencent_provider_requires_credentials_before_sdk_call(self) -> None:
        with patch(
            "app.integrations.tts.provider.get_settings",
            return_value=settings(tencentcloud_secret_id="", tencentcloud_secret_key=""),
        ):
            provider = TencentTTSProvider()
        with self.assertRaises(TTSProviderError) as context:
            provider.synthesize("你好", "default")
        self.assertEqual(context.exception.code, "config_missing")
        self.assertIn("TENCENTCLOUD_SECRET_ID", context.exception.message)
        self.assertNotIn("key", context.exception.message)

    def test_tencent_provider_enforces_short_prompt_limit(self) -> None:
        with patch("app.integrations.tts.provider.get_settings", return_value=settings()):
            provider = TencentTTSProvider()
        with self.assertRaises(TTSProviderError) as context:
            provider.synthesize("你" * 151, "default")
        self.assertEqual(context.exception.code, "text_too_long")

    def test_provider_factory_selects_tencent_and_rejects_unknown_names(self) -> None:
        with patch("app.integrations.tts.provider.get_settings", return_value=settings(tts_provider="tencent")):
            self.assertIsInstance(get_tts_provider(), TencentTTSProvider)
        with patch("app.integrations.tts.provider.get_settings", return_value=settings(tts_provider="unsupported")):
            with self.assertRaises(TTSProviderError) as context:
                get_tts_provider()
        self.assertEqual(context.exception.code, "unknown_provider")

    def test_windows_provider_writes_wav_via_local_sapi(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.integrations.tts.provider.get_settings", return_value=settings(storage_root=Path(temp_dir))):
                provider = WindowsTTSProvider()

            def fake_run(_command, **kwargs):
                Path(kwargs["env"]["SPEECH_REHAB_TTS_OUTPUT"]).write_bytes(b"R" * 45)
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            with patch("app.integrations.tts.provider.subprocess.run", side_effect=fake_run):
                path = Path(provider.synthesize("你好", "unused"))
            self.assertTrue(path.is_file())
            self.assertIn("windows_tts", path.name)

        with patch("app.integrations.tts.provider.get_settings", return_value=settings(tts_provider="windows")):
            self.assertIsInstance(get_tts_provider(), WindowsTTSProvider)

    def test_cache_name_is_stable_and_varies_by_voice_settings(self) -> None:
        first = avatar_speech_cache_name("tencent|default|502001|24000|-1", "请跟我说这一句。")
        second = avatar_speech_cache_name("tencent|default|502001|24000|-1", "请跟我说这一句。")
        changed_voice = avatar_speech_cache_name("tencent|default|602004|24000|-1", "请跟我说这一句。")
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed_voice)
        self.assertTrue(first.startswith("avatar_"))
        self.assertTrue(first.endswith(".wav"))

    def test_tencent_quota_error_has_a_recovery_message(self) -> None:
        error = tencent_tts_error(RuntimeError("UnsupportedOperation.PkgExhausted: resource pack allowance has been exhausted"))
        self.assertEqual(error.code, "quota_exhausted")
        self.assertIn("额度", error.message)
        self.assertNotIn("PkgExhausted", error.message)


if __name__ == "__main__":
    unittest.main()
