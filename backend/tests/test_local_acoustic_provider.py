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


class LocalAcousticAnalysisProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        os.environ.setdefault("ACOUSTIC_DBA_CALIBRATION_OFFSET", "90")
        os.environ.setdefault("ACOUSTIC_VOICE_THRESHOLD_DBFS", "-45")

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


if __name__ == "__main__":
    unittest.main()
