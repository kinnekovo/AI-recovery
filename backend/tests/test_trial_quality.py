import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.modules.attempts.model import AnalysisStatus
from app.modules.therapist.service import summarize_trial_quality_attempts


def attempt(audio=True, status=AnalysisStatus.completed, quality="pass", provider_error=None):
    row_attempt = SimpleNamespace(
        audio_file_id=uuid4() if audio else None,
        analysis_status=status,
        audio_quality=quality,
    )
    analysis = SimpleNamespace(semantic_metrics={"asr_error_code": provider_error}) if provider_error else None
    return (row_attempt, analysis)


class TrialQualityTest(unittest.TestCase):
    def test_summarizes_trial_quality_rates(self) -> None:
        summary = summarize_trial_quality_attempts(
            5,
            3,
            [
                attempt(),
                attempt(audio=False, status=AnalysisStatus.pending, quality=None),
                attempt(status=AnalysisStatus.failed),
                attempt(quality="low_quality", provider_error="provider_error"),
            ],
        )

        self.assertEqual(summary["completion_rate"], 0.6)
        self.assertEqual(summary["attempt_count"], 4)
        self.assertEqual(summary["missing_audio_count"], 1)
        self.assertEqual(summary["missing_audio_rate"], 0.25)
        self.assertEqual(summary["failed_analysis_count"], 1)
        self.assertEqual(summary["low_quality_attempt_count"], 1)
        self.assertEqual(summary["provider_failure_count"], 1)

    def test_empty_trial_quality_rates_are_zero(self) -> None:
        summary = summarize_trial_quality_attempts(0, 0, [])

        self.assertEqual(summary["completion_rate"], 0.0)
        self.assertEqual(summary["missing_audio_rate"], 0.0)
        self.assertEqual(summary["low_quality_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
