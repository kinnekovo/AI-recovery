import math
import os
import tempfile
import unittest
import wave
from array import array

from app.core.config import get_settings
from app.modules.pronunciation.prosody import analyze_prosody


def write_wav(path: str, frequency: float | None) -> None:
    sample_rate = 16000
    duration_seconds = 1.6
    samples = array(
        "h",
        [
            int(10000 * math.sin(2 * math.pi * frequency * index / sample_rate)) if frequency else 0
            for index in range(int(sample_rate * duration_seconds))
        ],
    )
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def write_wav_with_pause(path: str) -> None:
    sample_rate = 16000
    samples = array("h")
    for duration, frequency in ((0.55, 200), (0.35, None), (0.75, 200)):
        for index in range(int(sample_rate * duration)):
            samples.append(int(10000 * math.sin(2 * math.pi * frequency * index / sample_rate)) if frequency else 0)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


class ProsodyTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["ACOUSTIC_VOICE_THRESHOLD_DBFS"] = "-45"
        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("ACOUSTIC_VOICE_THRESHOLD_DBFS", None)
        get_settings.cache_clear()

    def test_estimates_pitch_from_a_voiced_tone(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            path = file.name
        try:
            write_wav(path, 200)
            result = analyze_prosody(path)
        finally:
            os.remove(path)
        self.assertEqual(result["status"], "completed")
        self.assertAlmostEqual(result["f0_median_hz"], 200, delta=12)
        self.assertGreater(result["voiced_ratio"], 0.9)

    def test_marks_silence_as_unavailable(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            path = file.name
        try:
            write_wav(path, None)
            result = analyze_prosody(path)
        finally:
            os.remove(path)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "insufficient_voiced_frames")
        self.assertIsNone(result["f0_median_hz"])

    def test_reports_internal_pause_and_rhythm_evidence(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            path = file.name
        try:
            write_wav_with_pause(path)
            result = analyze_prosody(path)
        finally:
            os.remove(path)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["pause_count"], 1)
        self.assertGreater(result["internal_pause_seconds"], 0.25)
        self.assertGreater(result["pause_ratio"], 0.1)
        self.assertIsNotNone(result["rhythm_interval_cv"])


if __name__ == "__main__":
    unittest.main()
