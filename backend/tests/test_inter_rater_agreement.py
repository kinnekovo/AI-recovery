import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.modules.therapist.service import summarize_inter_rater_agreement


class InterRaterAgreementTest(unittest.TestCase):
    def test_uses_only_the_latest_review_from_each_reviewer_per_attempt(self) -> None:
        analysis_id = uuid4()
        reviewer_a, reviewer_b = uuid4(), uuid4()
        reviews = [
            SimpleNamespace(analysis_id=analysis_id, recorded_by_user_id=reviewer_a, understood_percent=70, listener_transcript="今天天气好"),
            SimpleNamespace(analysis_id=analysis_id, recorded_by_user_id=reviewer_a, understood_percent=50, listener_transcript="旧记录"),
            SimpleNamespace(analysis_id=analysis_id, recorded_by_user_id=reviewer_b, understood_percent=80, listener_transcript="今天天气好"),
        ]

        result = summarize_inter_rater_agreement(reviews)

        self.assertEqual(result["listener_review_count"], 3)
        self.assertEqual(result["double_labeled_attempt_count"], 1)
        self.assertEqual(result["comparison_count"], 1)
        self.assertEqual(result["mean_absolute_percent_difference"], 10.0)
        self.assertEqual(result["within_ten_percent_rate"], 1.0)
        self.assertEqual(result["mean_transcript_similarity"], 1.0)

    def test_reports_insufficient_data_without_a_second_reviewer(self) -> None:
        review = SimpleNamespace(analysis_id=uuid4(), recorded_by_user_id=uuid4(), understood_percent=80, listener_transcript="测试")

        result = summarize_inter_rater_agreement([review])

        self.assertEqual(result["comparison_count"], 0)
        self.assertIsNone(result["mean_absolute_percent_difference"])
        self.assertIn("尚未形成", result["summary"])


if __name__ == "__main__":
    unittest.main()
