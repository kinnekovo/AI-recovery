from app.core.config import get_settings


class ASRProvider:
    provider_name = "base"

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError


class MockASRProvider(ASRProvider):
    provider_name = "mock"

    def __init__(self, requested_provider: str = "mock") -> None:
        self.requested_provider = requested_provider

    def transcribe(self, audio_path: str) -> str:
        return "这是一次模拟转写结果"


def get_asr_provider() -> ASRProvider:
    settings = get_settings()
    # Real ASR providers will be added behind this factory. Until then, every
    # non-mock value falls back to mock so the training loop keeps working.
    return MockASRProvider(requested_provider=settings.asr_provider)
