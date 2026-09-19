import unittest
from types import SimpleNamespace
from uuid import uuid4
from app.modules.assessment.comparability import compare
from app.modules.evaluation_runs.clinical_stage_v3 import build_payload
from app.modules.assessment.schema import ClinicalSourceUpdate
from app.modules.therapist import service as therapist_service
from fastapi import HTTPException
from unittest.mock import patch

def assessment(**kw):
 base=dict(id=uuid4(),patient_profile_id=uuid4(),source_attempt_id=None,assessment_type="baseline",evaluation_source="human",reviewed_by_user_id=None,reviewed_at=None,notes=None,therapist_notes=None,created_at="2026-01-01",instrument_name="WAB",instrument_version="v1",language_locale="zh-CN",localization_version="zh-v1",assessment_stage="baseline",assessed_at="2026-01-01",administered_by_user_id=uuid4(),administrator_role="therapist",raw_item_results={"x":1},subscale_results={"language":{"value":8}},total_result={"value":10},missing_items=[],score_unit="points",administration_mode="in_person",device_and_environment={},duration_seconds=60,protocol_deviations={},protocol_deviation_reasons=[],metrics={"wab_comprehensibility":7,"acceptance_score":4},review_status="confirmed")
 base.update(kw); return SimpleNamespace(**base)

class ClinicalStageV3Test(unittest.TestCase):
 def test_formal_separate_manual_dimensions_and_no_synthesized_overall(self):
  p=build_payload(assessment()); d={x.dimension_code:x for x in p.dimensions}
  self.assertEqual(p.result_status,"formal"); self.assertIn("manual_intelligibility.wab_comprehensibility",d); self.assertIn("acceptability",d); self.assertNotIn("overall_score",p.config_snapshot)
 def test_unknown_version_unit_and_empty_are_not_formal(self):
  self.assertEqual(build_payload(assessment(instrument_version=None)).result_status,"review_required")
  self.assertEqual(build_payload(assessment(score_unit=None)).result_status,"review_required")
  self.assertEqual(build_payload(assessment(total_result={},subscale_results={},metrics={})).result_status,"unscorable")
 def test_missing_is_not_zero(self):
  p=build_payload(assessment(subscale_results={"language":None},missing_items=["item-1"])); x=next(x for x in p.dimensions if x.dimension_code.endswith("language")); self.assertEqual(x.status,"unavailable"); self.assertIsNone(x.value)
 def test_comparability_explicit_reasons_and_partial_dimensions(self):
  a,b=assessment(),assessment(subscale_results={"language":{"value":10},"extra":None},missing_items=["item-x"])
  r=compare(a,b); self.assertEqual(r["status"],"partially_comparable"); self.assertIn("missing_required_items",r["reason_codes"]); self.assertEqual(r["compared_dimensions"][0]["change"],2)
  self.assertIn("scale_mismatch",compare(a,assessment(instrument_name="CADL"))["reason_codes"])
  self.assertIn("scale_version_mismatch",compare(a,assessment(instrument_version="v2"))["reason_codes"])
  self.assertIn("unit_mismatch",compare(a,assessment(score_unit="%"))["reason_codes"])
 def test_comparability_legacy_conditions_deviation_and_no_dimension(self):
  a=assessment(); self.assertIn("legacy_insufficient_metadata",compare(a,assessment(instrument_version=None))["reason_codes"])
  self.assertIn("administration_condition_changed",compare(a,assessment(administration_mode="remote"))["reason_codes"])
  self.assertIn("protocol_deviation",compare(a,assessment(protocol_deviation_reasons=["prompted"]))["reason_codes"])
  self.assertEqual(compare(a,assessment(subscale_results={}))["status"],"not_comparable")
 def test_source_update_policy_rejects_finalized_and_regenerates_pending(self):
  finalized=assessment(review_status="confirmed",therapist_notes=None)
  with patch("app.modules.therapist.service.get_owned_assessment",return_value=finalized):
   with self.assertRaises(HTTPException) as e: therapist_service.update_clinical_source(type("Db",(),{})(),assessment(),uuid4(),uuid4(),ClinicalSourceUpdate(score_unit="%"))
  self.assertEqual(e.exception.status_code,409)
  pending=assessment(review_status="pending_review",therapist_notes=None)
  class Db:
   def commit(self): pass
   def refresh(self,*_): pass
  with patch("app.modules.therapist.service.get_owned_assessment",return_value=pending), patch("app.modules.therapist.service._write_clinical_stage_shadow") as shadow:
   result=therapist_service.update_clinical_source(Db(),assessment(),uuid4(),uuid4(),ClinicalSourceUpdate(score_unit="%",revision_reason="correct unit"))
  self.assertEqual(pending.score_unit,"%"); shadow.assert_called_once(); self.assertIn("correct unit",pending.therapist_notes); self.assertEqual(result.score_unit,"%")
 def test_shadow_failure_isolated_and_persisted(self):
  class Db:
   def __init__(self): self.rolled=False
   def rollback(self): self.rolled=True
  db=Db(); a=assessment()
  with patch("app.modules.evaluation_runs.clinical_stage_v3.write_clinical_stage_run",side_effect=RuntimeError("bad")), patch("app.modules.evaluation_runs.service.record_evaluation_write_failure") as record:
   therapist_service._write_clinical_stage_shadow(db,a)
  self.assertTrue(db.rolled); record.assert_called_once()

if __name__=="__main__": unittest.main()
