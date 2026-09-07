import math
import os
import tempfile
import unittest
import wave
from array import array

from app.core.config import get_settings
from app.integrations.acoustic_analysis.provider import LocalAcousticAnalysisProvider


def write_test_wav(path: str) -> None:
    sample_rate = 16000
    samples = array("h")

    def append_tone(seconds: float, amplitude: int = 9000) -> None:
        for index in range(int(sample_rate * seconds)):
            value = int(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
            samples.append(value)

    def append_silence(seconds: float) -> None:
        samples.extend([0] * int(sample_rate * seconds))

    append_tone(1.0)
    append_silence(3.2)
    append_tone(1.0)

    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def write_wav(path: str, samples: array, sample_rate: int = 16000) -> None:
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


class LocalAcousticAnalysisProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        os.environ["ACOUSTIC_DBA_CALIBRATION_OFFSET"] = "90"
        os.environ["ACOUSTIC_VOICE_THRESHOLD_DBFS"] = "-45"
        os.environ["ACOUSTIC_MIN_SPEAKING_SECONDS"] = "1.0"
        os.environ["ACOUSTIC_MIN_LOUDNESS_DBA"] = "45"

    def tearDown(self) -> None:
        for key in (
            "ACOUSTIC_DBA_CALIBRATION_OFFSET",
            "ACOUSTIC_VOICE_THRESHOLD_DBFS",
            "ACOUSTIC_MIN_SPEAKING_SECONDS",
            "ACOUSTIC_MIN_LOUDNESS_DBA",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_analyzes_speaking_duration_pause_and_loudness(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio_path = temp_file.name
        try:
            write_test_wav(audio_path)
            result = LocalAcousticAnalysisProvider().analyze(audio_path)
        finally:
            os.remove(audio_path)

        self.assertGreaterEqual(result.speaking_duration_seconds, 1.8)
        self.assertLessEqual(result.speaking_duration_seconds, 2.2)
        self.assertEqual(result.long_pause_over_3s_count, 1)
        self.assertGreater(result.loudness_dba, 60)
        self.assertEqual(result.quality_status, "pass")
        self.assertFalse(result.too_short)
        self.assertFalse(result.too_quiet)

    def test_marks_short_audio_as_low_quality(self) -> None:
        sample_rate = 16000
        samples = array(
            "h",
            [int(9000 * math.sin(2 * math.pi * 440 * index / sample_rate)) for index in range(int(sample_rate * 0.25))],
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio_path = temp_file.name
        try:
            write_wav(audio_path, samples)
            result = LocalAcousticAnalysisProvider().analyze(audio_path)
        finally:
            os.remove(audio_path)

        self.assertEqual(result.quality_status, "low_quality")
        self.assertEqual(result.quality_reason, "too_short")
        self.assertTrue(result.too_short)
        self.assertFalse(result.too_quiet)

    def test_marks_silence_as_short_and_quiet(self) -> None:
        samples = array("h", [0] * 16000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio_path = temp_file.name
        try:
            write_wav(audio_path, samples)
            result = LocalAcousticAnalysisProvider().analyze(audio_path)
        finally:
            os.remove(audio_path)

        self.assertEqual(result.quality_status, "low_quality")
        self.assertEqual(result.quality_reason, "too_short_and_quiet")
        self.assertTrue(result.too_short)
        self.assertTrue(result.too_quiet)


if __name__ == "__main__":
    unittest.main()
