import unittest
from app.modules.calibration.analysis import continuous,patient_split,reliability,decision,PROMOTION_POLICY,classification,stability,reference,weighted_kappa,icc_3_1,assessment_stability
class CalibrationAnalysisTest(unittest.TestCase):
 def test_hand_calculated_continuous_metrics(self):
  r=continuous([1,3],[2,1]);self.assertEqual(r["mae"],1.5);self.assertEqual(r["bias"],.5);self.assertAlmostEqual(r["rmse"],2.5**.5)
 def test_patient_split_is_deterministic_and_nonleaking(self):
  s=[{"patient_profile_id":x} for x in ["a","a","b","c","d"]];a=patient_split(s,5,.25);b=patient_split(s,5,.25);self.assertEqual(a,b);self.assertFalse(set(a["development_patients"])&set(a["holdout_patients"]))
 def test_reliability_and_promotion_reasons(self):
  self.assertTrue(reliability([])["reference_unstable"])
  self.assertEqual(icc_3_1([(1,1),(2,2)]),1.0)
  d,reasons=decision({"n":1,"mae":20,"bias":8,"pearson":.1},{"n":0},{"reference_unstable":True},{},PROMOTION_POLICY,True);self.assertEqual(d,"insufficient_evidence");self.assertIn("provider_version_changed",reasons);self.assertIn("mae_above_threshold",reasons)
  d,reasons=decision({"n":20,"mae":1,"bias":0,"pearson":.9},{"n":5},{"reference_unstable":False},{},PROMOTION_POLICY,False);self.assertEqual(d,"eligible");self.assertEqual(reasons,[])
  d,reasons=decision({"n":20,"mae":1,"bias":0,"pearson":.9},{"n":5},{"reference_unstable":False},{"a":{"status":"ok","mae":1},"b":{"status":"ok","mae":20}},PROMOTION_POLICY,False);self.assertIn("subgroup_disparity",reasons)
 def test_classification_adjudication_and_comparable_stability(self):
  self.assertEqual(classification(["a","b"],["a","a"])["accuracy"],.5)
  self.assertEqual(weighted_kappa([1,2,3],[1,2,3]),1.0)
  self.assertEqual(reference([{"value":1},{"value":3,"is_adjudicated":True}]),(3,"adjudicated"))
  self.assertEqual(stability([(1,2),(1,9)],[{"status":"comparable"},{"status":"not_comparable"}])["mean_absolute_difference"],1)
  a=type("A",(),{"instrument_name":"x","instrument_version":"v","language_locale":"zh","localization_version":"l","score_unit":"p","protocol_deviation_reasons":[],"missing_items":[],"administration_mode":"in_person","subscale_results":{"z":1}})()
  b=type("A",(),{"instrument_name":"y","instrument_version":"v","language_locale":"zh","localization_version":"l","score_unit":"p","protocol_deviation_reasons":[],"missing_items":[],"administration_mode":"in_person","subscale_results":{"z":2}})()
  self.assertEqual(assessment_stability([(a,b,1,9)])["n"],0)
if __name__=="__main__":unittest.main()
