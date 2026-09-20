import unittest
from types import SimpleNamespace
from app.modules.policy_validation.analysis import feedback_stats,safety,promotion,patient_split
from app.modules.policy_v2.rules import RULESETS
from app.modules.policy_v2.model import PolicyDecision
from app.modules.policy_validation.analysis import VALIDATION_STATUSES
class T(unittest.TestCase):
 def test_feedback_unreviewed_not_disagree(self):
  r=feedback_stats([SimpleNamespace(agreement="agree")],3);self.assertEqual(r["unreviewed"],2);self.assertEqual(r["disagree"],0)
 def test_safety_rejects_nonshadow_and_forbidden(self):self.assertEqual(safety({"diagnosis":"x"},"active")["status"],"failed")
 def test_promotion_conservative(self):self.assertEqual(promotion({"total":0,"patients":0,"feedback":{"reviewed":0},"observed":0},"passed")["status"],"insufficient_evidence")
 def test_patient_split_is_deterministic_and_disjoint(self):
  a=patient_split(["a","b","a"],"x");self.assertEqual(a,patient_split(["b","a"],"x"));self.assertFalse(set(a["development"])&set(a["holdout"]))
 def test_ruleset_is_version_addressable(self):self.assertIn("policy-rules-v1",RULESETS)
 def test_validation_cannot_remove_shadow_runtime_guard(self):
  self.assertIn("mode = 'shadow'",str(PolicyDecision.__table_args__[0].sqltext))
 def test_validation_status_has_no_active_runtime_value(self):self.assertNotIn("active",VALIDATION_STATUSES)
if __name__=="__main__":unittest.main()
