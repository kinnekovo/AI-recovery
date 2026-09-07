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
            loudness=66.0,
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
            loudness=55.0,
        )

        feedback = safe_llm_feedback(FailingFeedbackProvider(), "目标句", "转写句", "repeat", process)

        self.assertIn("脚本完成度", feedback["main_strength"])
        self.assertTrue(feedback["suggestion"])
        self.assertNotEqual(feedback["suggestion"], "provider failed")


if __name__ == "__main__":
    unittest.main()
