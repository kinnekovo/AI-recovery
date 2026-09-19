import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import create_app
from app.modules.users.service import require_therapist
from app.modules.users.model import User,UserRole

class CalibrationApiTest(unittest.TestCase):
 def setUp(self):
  self.app=create_app();self.user=User(id=uuid4(),username="cal",password_hash="x",role=UserRole.therapist);self.app.dependency_overrides[require_therapist]=lambda:self.user;self.c=TestClient(self.app)
 def test_patient_facing_auth_cannot_reach_dataset_service(self):
  with patch("app.modules.calibration.router.service.dataset_read") as read:
   self.app.dependency_overrides[require_therapist]=lambda: (_ for _ in ()).throw(HTTPException(403))
   r=self.c.get(f"/api/calibration/datasets/{uuid4()}")
  self.assertEqual(r.status_code,403);read.assert_not_called()
 def test_read_and_metric_history_delegate_to_service(self):
  did=uuid4()
  with patch("app.modules.calibration.router.service.dataset_read",return_value={"id":str(did),"status":"frozen","sample_count":2}):
   r=self.c.get(f"/api/calibration/datasets/{did}")
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()["data"]["status"],"frozen")
  with patch("app.modules.calibration.router.service.metric_read",return_value={"metric_code":"x","status":"shadow","calibration_runs":[]}):
   r=self.c.get("/api/calibration/metrics/x")
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()["data"]["metric_code"],"x")
 def test_report_is_professional_only_and_delegated(self):
  rid=uuid4()
  with patch("app.modules.calibration.router.service.run_report",return_value={"run_id":str(rid),"promotion":{"decision":"insufficient_evidence"}}):
   r=self.c.get(f"/api/calibration/runs/{rid}/report")
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()["data"]["promotion"]["decision"],"insufficient_evidence")
if __name__=="__main__":unittest.main()
