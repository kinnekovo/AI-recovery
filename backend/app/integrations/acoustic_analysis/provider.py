from dataclasses import dataclass


@dataclass(frozen=True)
class AcousticAnalysisResult:
    speaking_duration_seconds: float
    loudness_dba: float
    long_pause_over_3s_count: int


class AcousticAnalysisProvider:
    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        raise NotImplementedError


class MockAcousticAnalysisProvider(AcousticAnalysisProvider):
    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        return AcousticAnalysisResult(
            speaking_duration_seconds=3.8,
            loudness_dba=65.0,
            long_pause_over_3s_count=1,
        )


def get_acoustic_analysis_provider() -> AcousticAnalysisProvider:
    return MockAcousticAnalysisProvider()
