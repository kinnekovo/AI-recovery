import unittest
from types import SimpleNamespace

from app.core.algorithm_config import ALGORITHM_CONFIG
from app.modules.evaluations.evidence_gate import process_evidence_gate
from app.modules.evaluations.schema import ProcessEvaluation
from app.modules.scoring.service import build_rule_score_dimensions
from app.modules.training.model import TrainingType
from app.modules.training.recommendation_policy import (
    RECOMMENDATION_POLICY,
    RecommendationDecision,
    TrendPolicyResult,
    apply_adaptive_adjustment,
    decide_recommendation_by_policy,
    metric_closer_to_range,
)
from app.modules.training.schema import TrainingRecommendationRead
from app.modules.training.service import family_voice_percent


def semantic_metrics(*, asr="tencent", acoustic="local", fallback=False, unit="dBFS", quality="pass"):
    return {
        "asr_provider": asr,
        "asr_fallback_used": fallback,
        "process_monitoring": {
            "details": {
                "evaluation_source": "system_rule",
                "provider_version": "rehab-process-v2",
                "quality_status": quality,
                "loudness_unit": unit,
                "input_sources": {"asr_provider": asr, "acoustic_provider": acoustic},
            }
        },
    }


def trend(status: str) -> TrendPolicyResult:
    return TrendPolicyResult(
        status=status,
        summary="",
        hint="",
        evidence=[],
        attribution_points=[],
        reminder_level="info",
        patient_reminder="",
        family_reminder="",
        therapist_reminder="",
    )


class R0AlgorithmSafetyTest(unittest.TestCase):
    def test_dbfs_reference_never_uses_legacy_60_or_69_target(self) -> None:
        loudness_config = ALGORITHM_CONFIG["repeat_loudness_reference"]
        self.assertEqual(loudness_config["unit"], "dBFS")
        self.assertEqual(loudness_config["value"], {"min": -35.0, "max": -12.0})
        self.assertNotIn("target_loudness", RECOMMENDATION_POLICY)
        self.assertTrue(metric_closer_to_range(-20.0, -40.0, (-35.0, -12.0), 0))
        self.assertEqual(family_voice_percent(-20.0), 100)

        ability = SimpleNamespace(
            avg_script_accuracy_recent=90.0,
            avg_error_count_recent=1.0,
            avg_speech_rate_recent=200.0,
            avg_loudness_recent=-24.0,
            current_content_level="L2",
            current_autonomy_level="S2",
            evidence={"loudness_unit": "dBFS", "profile_eligibility": True, "reviewed_assessment_count": 0},
        )
        decision = decide_recommendation_by_policy(ability)
        self.assertNotEqual(decision.headline, "先练声音稳定")

    def test_mock_fallback_and_low_quality_are_not_decision_eligible(self) -> None:
        self.assertFalse(process_evidence_gate("pass", semantic_metrics(asr="mock"), "rehab-process-v2").eligible)
        self.assertFalse(process_evidence_gate("pass", semantic_metrics(fallback=True), "rehab-process-v2").eligible)
        self.assertFalse(process_evidence_gate("low_quality", semantic_metrics(quality="low_quality"), "rehab-process-v2").eligible)

        ability = SimpleNamespace(
            avg_script_accuracy_recent=95.0,
            avg_error_count_recent=0.0,
            avg_speech_rate_recent=210.0,
            avg_loudness_recent=-24.0,
            current_content_level="L2",
            current_autonomy_level="S2",
            evidence={"loudness_unit": "dBFS", "profile_eligibility": False},
        )
        decision = decide_recommendation_by_policy(ability, trend("effective"))
        self.assertEqual((decision.content_level, decision.autonomy_level), ("L2", "S2"))
        self.assertIn("安全门控", decision.adaptation_note or "")

    def test_unknown_unit_stops_formal_decision(self) -> None:
        gate = process_evidence_gate("pass", semantic_metrics(unit=None), "rehab-process-v2")
        self.assertFalse(gate.eligible)
        self.assertIn("loudness_unit_unknown_or_incompatible", gate.reasons)

        process = ProcessEvaluation(script_accuracy=90, error_count=0, speech_rate=200, loudness=-24, details={})
        with self.assertRaisesRegex(ValueError, "dBFS"):
            build_rule_score_dimensions(process)

        ability = SimpleNamespace(
            avg_script_accuracy_recent=95.0,
            avg_error_count_recent=0.0,
            avg_speech_rate_recent=210.0,
            avg_loudness_recent=-24.0,
            current_content_level="L3",
            current_autonomy_level="S3",
            evidence={"profile_eligibility": True},
        )
        decision = decide_recommendation_by_policy(ability, trend("effective"))
        self.assertEqual((decision.content_level, decision.autonomy_level), ("L3", "S3"))
        self.assertIn("单位不明", decision.adaptation_note or "")

    def test_phase43_no_longer_changes_formal_difficulty(self) -> None:
        baseline = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="保持",
            reason="保持。",
            focus_points=["保持"],
            suggested_minutes=10,
            content_level="L3",
            autonomy_level="S2",
        )
        for status in ("effective", "needs_adjustment"):
            decision = apply_adaptive_adjustment(baseline, trend(status))
            self.assertEqual((decision.content_level, decision.autonomy_level), ("L3", "S2"))
            self.assertEqual(decision.suggested_minutes, 10)

    def test_legacy_recommendation_api_shape_remains_compatible(self) -> None:
        recommendation = TrainingRecommendationRead(
            recommended_type=TrainingType.repeat,
            headline="保持训练",
            reason="历史兼容",
            focus_points=["完成一组"],
            suggested_minutes=8,
            content_level="L1",
            autonomy_level="S1",
            confidence=0.0,
            profile_summary="证据积累中",
        )
        payload = recommendation.model_dump(mode="json")
        for field in (
            "recommended_type",
            "headline",
            "reason",
            "focus_points",
            "suggested_minutes",
            "content_level",
            "autonomy_level",
            "confidence",
            "profile_summary",
            "policy_version",
        ):
            self.assertIn(field, payload)


if __name__ == "__main__":
    unittest.main()
