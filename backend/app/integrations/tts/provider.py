import math
import wave
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


class TTSProvider:
    name = "base"

    def synthesize(self, text: str, voice_id: str) -> str:
        raise NotImplementedError


class MockTTSProvider(TTSProvider):
    name = "mock"

    def synthesize(self, text: str, voice_id: str) -> str:
        output_dir = get_settings().storage_root / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"speech_{uuid4().hex}.wav"
        sample_rate = 16000
        duration_seconds = 1.2
        frames = int(sample_rate * duration_seconds)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for index in range(frames):
                value = int(16000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                wav.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
        return str(path)


def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.tts_provider != "mock":
        return MockTTSProvider()
    return MockTTSProvider()
