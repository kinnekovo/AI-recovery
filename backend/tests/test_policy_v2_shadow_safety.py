import unittest
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import import_models
from app.modules.policy_v2.engine import decide
from app.modules.policy_v2.model import PolicyDecision
from app.modules.policy_v2 import service

class PolicyV2ShadowSafetyTest(unittest.TestCase):
 def setUp(self):
  import_models();self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);PolicyDecision.__table__.create(self.engine);self.db=sessionmaker(bind=self.engine,expire_on_commit=False)()
  self.pid=uuid4();self.profile={"snapshot_id":str(uuid4()),"profile_version":"profile-v2.0","mapping_version":"profile-mapping-v1","evidence_policy_version":"profile-evidence-policy-v1","generated_at":datetime.now(timezone.utc).isoformat(),"status":"complete","dimensions":[{"code":"repeat.content_reproduction","current_value":0,"unit":"%","trend":"falling","evidence_sufficiency":"sufficient"}]}
 def tearDown(self):self.db.close();self.engine.dispose()
 def test_shadow_generation_is_idempotent_and_never_active(self):
  with patch("app.modules.policy_v2.service.get_policy_profile",return_value=self.profile),patch("app.modules.policy_v2.service._resolve_failure"):
   first=service.generate_shadow(self.db,self.pid);second=service.generate_shadow(self.db,self.pid)
  self.assertEqual(first.id,second.id);self.assertEqual(first.mode,"shadow");self.assertEqual(self.db.query(PolicyDecision).count(),1)
 def test_engine_does_not_mutate_legacy_training_input(self):
  legacy={"content_level":"L3","autonomy_level":"S2","tasks":["unchanged"]};before=deepcopy(legacy)
  output=decide(self.profile);self.assertEqual(legacy,before);self.assertEqual(output["mode"],"shadow")
if __name__=="__main__":unittest.main()
