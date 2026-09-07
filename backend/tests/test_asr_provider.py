import os
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from app.core.config import get_settings
from app.integrations.asr.provider import ASRProviderError, TencentASRProvider, transcribe_with_fallback


class ASRProviderFallbackTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ("ASR_PROVIDER", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_tencent_config_error_stops_scoring_instead_of_falling_back(self) -> None:
        os.environ["ASR_PROVIDER"] = "tencent"
        os.environ["TENCENTCLOUD_SECRET_ID"] = ""
        os.environ["TENCENTCLOUD_SECRET_KEY"] = ""
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(b"fake-audio")
            audio.flush()
            with self.assertRaisesRegex(ASRProviderError, "TENCENTCLOUD_SECRET_ID") as raised:
                transcribe_with_fallback(audio.name)

        self.assertEqual(raised.exception.code, "config_missing")

    def test_unknown_provider_uses_mock_without_error(self) -> None:
        os.environ["ASR_PROVIDER"] = "not-real"
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            result = transcribe_with_fallback(audio.name)

        self.assertEqual(result.provider_name, "mock")
        self.assertEqual(result.requested_provider, "not-real")
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.error_code)

    def test_tencent_prepares_browser_audio_as_wav(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
        os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".webm") as audio:
            audio.write(b"webm-placeholder")
            audio.flush()

            def fake_transcode(command, check, capture_output):
                Path(command[-1]).write_bytes(b"wav-placeholder")
                return CompletedProcess(command, 0)

            provider = TencentASRProvider()
            with patch("app.integrations.asr.provider.subprocess.run", side_effect=fake_transcode) as run:
                prepared, voice_format = provider._prepare_audio(audio.name)
            try:
                self.assertEqual(voice_format, "wav")
                self.assertEqual(prepared.read_bytes(), b"wav-placeholder")
                command = run.call_args.args[0]
                self.assertIn("16000", command)
                self.assertIn("pcm_s16le", command)
                self.assertEqual(command[-1], str(prepared))
            finally:
                prepared.unlink(missing_ok=True)

    def test_tencent_transcodes_audio_to_valid_wav_locally(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
        os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
        get_settings.cache_clear()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio_path = temp_file.name
        try:
            with wave.open(audio_path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(array("h", [0, 1000, -1000] * 1600).tobytes())

            prepared, voice_format = TencentASRProvider()._prepare_audio(audio_path)
            try:
                self.assertEqual(voice_format, "wav")
                self.assertEqual(prepared.read_bytes()[:4], b"RIFF")
            finally:
                prepared.unlink(missing_ok=True)
        finally:
            Path(audio_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
