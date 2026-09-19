import unittest

from app.modules.profiles.service import is_profile_eligible_analysis


def semantic_metrics(asr_provider: str = "tencent", acoustic_provider: str = "local", fallback: bool = False) -> dict:
    return {
        "asr_provider": asr_provider,
        "asr_fallback_used": fallback,
        "process_monitoring": {
            "details": {
                "evaluation_source": "system_rule",
                "provider_version": "rehab-process-v2",
                "quality_status": "pass",
                "loudness_unit": "dBFS",
                "input_sources": {
                    "asr_provider": asr_provider,
                    "acoustic_provider": acoustic_provider,
                },
            },
        },
    }


class ProfileDataQualityTest(unittest.TestCase):
    def test_accepts_real_passed_analysis(self) -> None:
        self.assertTrue(is_profile_eligible_analysis("pass", semantic_metrics()))

    def test_rejects_low_quality_audio(self) -> None:
        self.assertFalse(is_profile_eligible_analysis("low_quality", semantic_metrics()))

    def test_rejects_asr_fallback(self) -> None:
        self.assertFalse(is_profile_eligible_analysis("pass", semantic_metrics(fallback=True)))

    def test_rejects_mock_asr_or_acoustic_sources(self) -> None:
        self.assertFalse(is_profile_eligible_analysis("pass", semantic_metrics(asr_provider="mock")))
        self.assertFalse(is_profile_eligible_analysis("pass", semantic_metrics(acoustic_provider="mock")))

    def test_rejects_mock_process_evaluation(self) -> None:
        metrics = semantic_metrics()
        metrics["process_monitoring"]["details"]["evaluation_source"] = "mock_ai"

        self.assertFalse(is_profile_eligible_analysis("pass", metrics))

    def test_rejects_unknown_loudness_unit(self) -> None:
        metrics = semantic_metrics()
        metrics["process_monitoring"]["details"].pop("loudness_unit")

        self.assertFalse(is_profile_eligible_analysis("pass", metrics))


if __name__ == "__main__":
    unittest.main()
