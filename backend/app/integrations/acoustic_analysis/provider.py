from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class AcousticAnalysisResult:
    speaking_duration_seconds: float
    loudness_dba: float
    long_pause_over_3s_count: int


class AcousticAnalysisProvider:
    provider_name = "base"

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        raise NotImplementedError


class MockAcousticAnalysisProvider(AcousticAnalysisProvider):
    provider_name = "mock"

    def __init__(self, requested_provider: str = "mock") -> None:
        self.requested_provider = requested_provider

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        return AcousticAnalysisResult(
            speaking_duration_seconds=3.8,
            loudness_dba=65.0,
            long_pause_over_3s_count=1,
        )


def get_acoustic_analysis_provider() -> AcousticAnalysisProvider:
    settings = get_settings()
    # Real acoustic providers will be added behind this factory. Until then,
    # non-mock values fall back to mock without changing process metric names.
    return MockAcousticAnalysisProvider(requested_provider=settings.acoustic_provider)
