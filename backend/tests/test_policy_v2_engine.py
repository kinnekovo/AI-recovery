import unittest
from datetime import datetime, timedelta, timezone
from app.modules.policy_v2.engine import decide
from app.modules.policy_v2.explain import explain

NOW=datetime(2026,9,19,tzinfo=timezone.utc)
def profile(dimensions, **extra):
 return {"snapshot_id":"00000000-0000-0000-0000-000000000001","profile_version":"profile-v2.0","mapping_version":"profile-mapping-v1","evidence_policy_version":"profile-evidence-policy-v1","generated_at":NOW.isoformat(),"status":"complete","dimensions":dimensions,**extra}
def dim(code="repeat.content_reproduction",trend="stable",state=None):
 return {"code":code,"current_value":0,"unit":"%","trend":trend,"evidence_sufficiency":"sufficient",**({"current_state":state} if state else {})}

class PolicyV2EngineTest(unittest.TestCase):
 def test_no_profile(self): self.assertEqual(decide(None,now=NOW)["input_status"],"insufficient_profile")
 def test_failed_profile_requires_refresh(self): self.assertEqual(decide({"status":"failed","profile_failure":True,"dimensions":[]},now=NOW)["input_status"],"profile_refresh_required")
 def test_sufficient_low_state_is_focus_candidate(self):
  out=decide(profile([dim(state="low")]),now=NOW);self.assertEqual(out["training_focus"][0]["priority"],"medium")
 def test_strong_stable_is_low_focus(self): self.assertEqual(decide(profile([dim()]),now=NOW)["training_focus"][0]["priority"],"low")
 def test_mixed_trend_requires_review_difficulty(self): self.assertEqual(decide(profile([dim(trend="mixed")]),now=NOW)["difficulty"]["recommended_difficulty_action"],"review_required")
 def test_falling_trend_decreases_shadow_only(self): self.assertEqual(decide(profile([dim(trend="falling")]),now=NOW)["difficulty"]["recommended_difficulty_action"],"decrease")
 def test_rising_trend_increases_shadow_only(self): self.assertEqual(decide(profile([dim(trend="rising")]),now=NOW)["difficulty"]["recommended_difficulty_action"],"increase")
 def test_insufficient_coverage(self): self.assertEqual(decide(profile([],status="insufficient"),now=NOW)["input_status"],"insufficient_input")
 def test_stale_profile_is_gated(self):
  p=profile([dim()]);p["generated_at"]=(NOW-timedelta(days=8)).isoformat();self.assertEqual(decide(p,now=NOW)["input_status"],"insufficient_input")
 def test_long_clinical_interval_consider_reassessment(self):
  p=profile([dim()],latest_clinical_assessment_at=(NOW-timedelta(days=200)).isoformat());self.assertEqual(decide(p,now=NOW)["reassessment"]["signal"],"consider_reassessment")
 def test_priority_order_is_deterministic(self):
  out=decide(profile([dim("z", "stable"),dim("b","falling"),dim("a","falling")]),now=NOW)
  self.assertEqual([x["dimension_code"] for x in out["training_focus"]],["a","b","z"])
 def test_explicit_reason_codes(self): self.assertIn("FALLING_TREND",decide(profile([dim(trend="falling")]),now=NOW)["reason_codes"])
 def test_explanation_is_deterministic_projection(self):
  output=decide(profile([dim(trend="falling")]),now=NOW);self.assertEqual(explain(output)["focus"][0]["dimension_code"],"repeat.content_reproduction")
if __name__=="__main__":unittest.main()
