import unittest

from app.modules.evaluations.schema import ProcessEvaluation
from app.modules.scoring.service import build_rule_score_dimensions, safe_llm_feedback


class UnsafeFeedbackProvider:
    provider_name = "unsafe"

    def evaluate(self, target_text: str, transcript: str, task_type: str) -> dict:
        return {
            "overall_score": 1,
            "content_score": 1,
            "clarity_score": 1,
            "main_strength": "表达内容较完整",
            "main_issue": "节奏偏慢",
            "suggestion": "下一次先放慢速度，把目标句说完整。",
        }


class FailingFeedbackProvider:
    provider_name = "failing"

    def evaluate(self, target_text: str, transcript: str, task_type: str) -> dict:
        raise RuntimeError("provider failed")


class LLMFeedbackBoundaryTest(unittest.TestCase):
    def test_scores_are_rule_based_not_provider_controlled(self) -> None:
        process = ProcessEvaluation(
            script_accuracy=92.0,
            error_count=1,
            speech_rate=200.0,
            loudness=-24.0,
            details={"loudness_unit": "dBFS"},
        )

        scores = build_rule_score_dimensions(process)
        feedback = safe_llm_feedback(UnsafeFeedbackProvider(), "目标句", "目标句", "repeat", process)

        self.assertGreater(scores["overall_score"], 80)
        self.assertEqual(feedback["main_strength"], "表达内容较完整")
        self.assertNotIn("overall_score", feedback)
        self.assertNotEqual(scores["overall_score"], 1)

    def test_provider_failure_falls_back_to_rule_feedback(self) -> None:
        process = ProcessEvaluation(
            script_accuracy=65.0,
            error_count=3,
            speech_rate=160.0,
            loudness=-40.0,
        )

        feedback = safe_llm_feedback(FailingFeedbackProvider(), "目标句", "转写句", "repeat", process)

        self.assertIn("脚本完成度", feedback["main_strength"])
        self.assertTrue(feedback["suggestion"])
        self.assertNotEqual(feedback["suggestion"], "provider failed")

    def test_scores_change_with_measured_performance(self) -> None:
        strong = ProcessEvaluation(
            script_accuracy=100.0,
            error_count=0,
            speech_rate=200.0,
            loudness=-24.0,
            details={
                "task_type": "repeat",
                "expression_rate": 200.0,
                "articulation_rate": 220.0,
                "loudness_unit": "dBFS",
                "independence_score": 100,
                "error_events": {},
            },
        )
        weak = ProcessEvaluation(
            script_accuracy=45.0,
            error_count=5,
            speech_rate=90.0,
            loudness=-48.0,
            details={
                "task_type": "repeat",
                "expression_rate": 90.0,
                "articulation_rate": 120.0,
                "loudness_unit": "dBFS",
                "independence_score": 30,
                "pause_metrics": {"pause_ratio": 0.5},
                "error_events": {"meaningless_repetition": 2, "long_pause_over_3s": 2},
            },
        )

        strong_scores = build_rule_score_dimensions(strong)
        weak_scores = build_rule_score_dimensions(weak)

        self.assertGreater(strong_scores["overall_score"], weak_scores["overall_score"] + 30)
        self.assertEqual(strong_scores["scoring_config"]["version"], "rehab-score-v2")

    def test_scenario_uses_task_specific_weights(self) -> None:
        process = ProcessEvaluation(
            script_accuracy=80.0,
            error_count=0,
            speech_rate=190.0,
            loudness=-24.0,
            details={"task_type": "scenario", "loudness_unit": "dBFS", "independence_score": 80},
        )

        scores = build_rule_score_dimensions(process)

        self.assertEqual(scores["scoring_config"]["task_type"], "scenario")
        self.assertEqual(scores["scoring_config"]["weights"]["independence"], 0.15)


if __name__ == "__main__":
    unittest.main()
