import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.profile_v2.mapping import PROFILE_EVIDENCE_POLICY_VERSION, PROFILE_MAPPING_VERSION, mapping_for
from app.modules.profile_v2.service import _eligible, _payload, _trend
from app.modules.profile_v2 import service as profile_service
from app.modules.profile_v2.model import PatientProfileSnapshot, ProfileEvidenceLink, ProfileBuildFailure
from app.modules.evaluation_runs.model import EvaluationRun, EvaluationDimensionResult
from app.modules.calibration.model import MetricRegistry
from app.modules.users.model import PatientProfile, User, UserRole
from app.modules.agents.model import Agent
from app.modules.files.model import FileAsset
from app.modules.attempts.model import Attempt
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.scoring.model import AttemptScore  # resolves legacy ORM relationships
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def run(domain="repeat", eligible=True, status="formal"):
    return SimpleNamespace(domain=domain, profile_eligibility=eligible, result_status=status)

def dim(code, value=0, unit="%", status="measured"):
    return SimpleNamespace(dimension_code=code, value=value, unit=unit, status=status)


class ProfileV2ContractTest(unittest.TestCase):
    def test_mapping_uses_real_v3_dimensions_and_is_versioned(self):
        item = mapping_for("functional_communication", "response_ability")
        self.assertEqual(item["profile_dimension_code"], "functional.response_ability")
        self.assertEqual(item["mapping_version"], PROFILE_MAPPING_VERSION)
        self.assertIsNone(mapping_for("repeat", "invented_metric"))

    def test_zero_is_a_measured_observation_and_not_observed_is_excluded(self):
        registry={"content_reproduction": SimpleNamespace(status="promoted")}
        mapped, reason = _eligible(run(), dim("content_reproduction", 0), registry)
        self.assertIsNotNone(mapped); self.assertIsNone(reason)
        mapped, reason = _eligible(run(), dim("content_reproduction", None, status="not_observed"), registry)
        self.assertIsNone(mapped); self.assertEqual(reason, "canonical_ineligible")

    def test_shadow_fallback_and_provisional_metric_do_not_formal_aggregate(self):
        for metric_status in ("experimental", "shadow", "suspended", "provisional"):
            mapped, reason = _eligible(run(), dim("content_reproduction", 80), {"content_reproduction": SimpleNamespace(status=metric_status)})
            self.assertIsNone(mapped); self.assertIn(metric_status, reason)

    def test_manual_clinical_evidence_does_not_need_metric_registry(self):
        mapped, reason = _eligible(run("clinical_stage"), dim("manual_intelligibility.word", 0, "%"), {})
        self.assertEqual(mapped["source_kind"], "clinical_manual"); self.assertIsNone(reason)

    def test_current_state_is_recent_window_not_all_history_mean(self):
        ts=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[]
        for i,value in enumerate([1,2,3,100]):
            rows.append({"profile_dimension_code":"repeat.content_reproduction","unit":"%","source_kind":"automatic","value":value,"timestamp":ts.replace(day=i+1),"direction":"high"})
        payload, status = _payload(rows, [])
        self.assertEqual(status,"complete")
        self.assertEqual(payload["dimensions"][0]["current_value"], 35.0)  # latest three, not all-history 26.5
        self.assertEqual(payload["evidence_policy_version"], PROFILE_EVIDENCE_POLICY_VERSION)

    def test_trend_does_not_claim_direction_when_mapping_is_unknown(self):
        rows=[{"value":1,"direction":"unknown"},{"value":2,"direction":"unknown"}]
        self.assertEqual(_trend(rows,"automatic"),("mixed","direction_unknown"))

    def test_manual_and_automatic_evidence_are_not_flattened(self):
        ts=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[{"profile_dimension_code":"clinical.acceptability","unit":"%","source_kind":"automatic","value":1,"timestamp":ts,"direction":"high"},
              {"profile_dimension_code":"clinical.acceptability","unit":"%","source_kind":"clinical_manual","value":2,"timestamp":ts,"direction":"high"}]
        payload,_=_payload(rows,[])
        self.assertEqual(len(payload["dimensions"]),2)

    def test_builder_is_immutable_and_idempotent(self):
        engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        tables=[User.__table__,PatientProfile.__table__,EvaluationRun.__table__,EvaluationDimensionResult.__table__,MetricRegistry.__table__,PatientProfileSnapshot.__table__,ProfileEvidenceLink.__table__,ProfileBuildFailure.__table__]
        for table in tables: table.create(engine)
        db=sessionmaker(bind=engine,expire_on_commit=False)()
        try:
            user=User(username="profile-v2-patient",password_hash="x",role=UserRole.patient);db.add(user);db.commit()
            patient=PatientProfile(user_id=user.id);db.add(patient);db.commit()
            db.add(MetricRegistry(metric_code="content_reproduction",display_name="content",source="test",version="v1",dimension_type="continuous",unit="%",status="promoted"))
            run_row=EvaluationRun(patient_profile_id=patient.id,domain="repeat",source_type="attempt",source_id=__import__("uuid").uuid4(),algorithm_version="repeat-v3",config_snapshot={},input_provenance={"providers":{}},quality_gate={"eligible":True},result_status="formal",profile_eligibility=True,profile_ineligibility_reasons=[],limitations=[],adoption_status="adopted")
            db.add(run_row);db.flush();db.add(EvaluationDimensionResult(evaluation_run_id=run_row.id,dimension_code="content_reproduction",value=0,unit="%",status="measured",measurement_quality={},evidence_snapshot={},limitations=[]));db.commit()
            one=profile_service.build_profile(db,patient.id); two=profile_service.build_profile(db,patient.id)
            self.assertEqual(one.id,two.id);self.assertEqual(db.query(PatientProfileSnapshot).count(),1);self.assertEqual(db.query(ProfileEvidenceLink).count(),1)
            self.assertEqual(one.payload["dimensions"][0]["current_value"],0.0)
        finally:
            db.close();engine.dispose()

if __name__ == "__main__": unittest.main()
