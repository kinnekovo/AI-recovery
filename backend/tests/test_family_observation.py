import unittest
from datetime import datetime

from app.modules.training.service import family_adherence_summary


class FamilyObservationTest(unittest.TestCase):
    def test_adherence_summary_for_no_training(self) -> None:
        self.assertIn("还没有训练记录", family_adherence_summary(0, 0, None))

    def test_adherence_summary_guides_recommended_training(self) -> None:
        summary = family_adherence_summary(3, 0, None)

        self.assertIn("已经练了 3 次", summary)
        self.assertIn("建议训练", summary)

    def test_adherence_summary_includes_latest_training_date(self) -> None:
        summary = family_adherence_summary(5, 4, datetime(2026, 9, 3, 9, 30))

        self.assertIn("已经练了 5 次", summary)
        self.assertIn("4 次完成建议训练", summary)
        self.assertIn("09月03日", summary)


if __name__ == "__main__":
    unittest.main()
