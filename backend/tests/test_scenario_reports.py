import unittest
from datetime import datetime, timezone

from app.modules.reports.service import build_scenario_communication_summary


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _ScenarioReportDb:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _statement):
        return _Rows(self.rows)


def _probe(at: datetime):
    return (
        {
            "process_monitoring": {
                "evaluation_source": "system_rule",
                "independence_score": 100,
                "scenario_evaluation": {
                    "evaluation_role": "generalization_probe",
                    "goal_status": "achieved",
                    "information_unit_score": 100,
                },
            }
        },
        None,
        at,
    )


class ScenarioReportTest(unittest.TestCase):
    def test_same_day_probes_do_not_claim_generalization(self) -> None:
        db = _ScenarioReportDb(
            [
                _probe(datetime(2026, 9, 8, 9, tzinfo=timezone.utc)),
                _probe(datetime(2026, 9, 8, 15, tzinfo=timezone.utc)),
            ]
        )

        result = build_scenario_communication_summary(db, "profile")

        self.assertEqual(result.generalization_probe_count, 2)
        self.assertEqual(result.generalization_probe_distinct_date_count, 1)
        self.assertIn("尚未覆盖两个不同日期", result.generalization_summary)

    def test_independent_probes_on_two_dates_can_signal_generalization(self) -> None:
        db = _ScenarioReportDb(
            [
                _probe(datetime(2026, 9, 8, 9, tzinfo=timezone.utc)),
                _probe(datetime(2026, 9, 10, 9, tzinfo=timezone.utc)),
            ]
        )

        result = build_scenario_communication_summary(db, "profile")

        self.assertEqual(result.generalization_probe_distinct_date_count, 2)
        self.assertIn("两个不同日期", result.generalization_summary)


if __name__ == "__main__":
    unittest.main()
