import unittest

from scripts.init_trial_data import planned_payload


class TrialDataScriptTest(unittest.TestCase):
    def test_planned_payload_matches_trial_counts(self) -> None:
        payload = planned_payload("temp", patient_count=5, family_count=3)

        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["accounts"]["admin"], "trial_admin")
        self.assertEqual(payload["accounts"]["therapist"], "trial_therapist_01")
        self.assertEqual(len(payload["accounts"]["patients"]), 5)
        self.assertEqual(len(payload["accounts"]["families"]), 3)
        self.assertEqual(payload["therapist_assignments"], 5)
        self.assertEqual(payload["pending_family_bindings"], 3)


if __name__ == "__main__":
    unittest.main()
