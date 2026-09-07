import unittest
from types import SimpleNamespace

from app.modules.attempts.model import AnalysisStatus
from app.modules.therapist.service import summarize_stage_attempt_rows


def row(status: AnalysisStatus = AnalysisStatus.completed, audio_quality: str | None = "pass", score=True, asr_error_code: str | None = None):
    attempt = SimpleNamespace(analysis_status=status, audio_quality=audio_quality)
    score_value = object() if score else None
    analysis = SimpleNamespace(semantic_metrics={"asr_error_code": asr_error_code}) if asr_error_code else None
    return (attempt, None, None, score_value, analysis)


class TherapistStageReportTest(unittest.TestCase):
    def test_summarizes_quality_failures_and_provider_failures(self) -> None:
        summary = summarize_stage_attempt_rows(
            [
                row(),
                row(audio_quality="low_quality"),
                row(status=AnalysisStatus.failed, score=False),
                row(asr_error_code="provider_error"),
            ]
        )

        self.assertEqual(summary["training_count"], 4)
        self.assertEqual(summary["analyzed_attempt_count"], 3)
        self.assertEqual(summary["failed_analysis_count"], 1)
        self.assertEqual(summary["low_quality_attempt_count"], 1)
        self.assertEqual(summary["low_quality_rate"], 0.25)
        self.assertEqual(summary["provider_failure_count"], 1)

    def test_empty_range_returns_zeroes(self) -> None:
        summary = summarize_stage_attempt_rows([])

        self.assertEqual(summary["training_count"], 0)
        self.assertEqual(summary["low_quality_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
