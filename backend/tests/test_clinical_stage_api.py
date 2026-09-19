import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.security import create_access_token
from app.modules.users.model import User, UserRole
from app.modules.users.service import require_therapist

class ClinicalStageApiTest(unittest.TestCase):
 def setUp(self):
  self.app=create_app(); self.client=TestClient(self.app); self.therapist=User(id=uuid4(),username="clinical-api",password_hash="x",role=UserRole.therapist); self.app.dependency_overrides[require_therapist]=lambda:self.therapist; self.pid=uuid4(); self.aid=uuid4()
  self.headers={"Authorization":"Bearer "+create_access_token(str(self.therapist.id))}
 def test_professional_routes_require_assignment_before_service(self):
  # Existing assignment guard is the only permission authority; a fake DB makes
  # it reject before data-bearing service execution.
  with patch("app.modules.therapist.router.service.require_therapist_patient_access", side_effect=__import__('fastapi').HTTPException(403)), patch("app.modules.therapist.router.service.clinical_stage_detail") as detail:
   r=self.client.get(f"/api/therapist/patients/{self.pid}/assessments/{self.aid}/clinical-stage",headers=self.headers)
  self.assertEqual(r.status_code,403); detail.assert_not_called()
 def test_preview_and_comparison_delegate_to_single_service_layer(self):
  with patch("app.modules.therapist.router.service.require_therapist_patient_access"), patch("app.modules.therapist.router.service.clinical_stage_detail",return_value={"canonical_preview":{"result_status":"review_required"}}):
   r=self.client.get(f"/api/therapist/patients/{self.pid}/assessments/{self.aid}/clinical-stage/preview",headers=self.headers)
  self.assertEqual(r.status_code,200); self.assertEqual(r.json()["data"]["result_status"],"review_required")
  with patch("app.modules.therapist.router.service.require_therapist_patient_access"), patch("app.modules.therapist.router.service.compare_clinical_stage",return_value={"status":"not_comparable","reason_codes":["unit_mismatch"]}):
   r=self.client.get(f"/api/therapist/patients/{self.pid}/assessments/{self.aid}/clinical-stage/comparison/{uuid4()}",headers=self.headers)
  self.assertEqual(r.status_code,200); self.assertEqual(r.json()["data"]["reason_codes"],["unit_mismatch"])

if __name__=="__main__": unittest.main()
