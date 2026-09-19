import unittest
from types import SimpleNamespace
from uuid import uuid4
from fastapi import HTTPException
from app.modules.calibration import service

class Db:
 def __init__(self,items):self.items=items;self.commits=0;self.deleted=[]
 def get(self,cls,key):return self.items.get((cls.__name__,key))
 def commit(self):self.commits+=1
 def delete(self,x):self.deleted.append(x)
class CalibrationLifecycleTest(unittest.TestCase):
 def test_freeze_transition_and_frozen_sample_mutation_rejected(self):
  did=uuid4();d=SimpleNamespace(id=did,status="draft",frozen_at=None);db=Db({("CalibrationDataset",did):d})
  service.freeze(db,SimpleNamespace(),did);self.assertEqual(d.status,"frozen");self.assertEqual(db.commits,1)
  with self.assertRaises(HTTPException):service.freeze(db,SimpleNamespace(),did)
 def test_remove_sample_is_draft_only_and_scoped(self):
  did,sid=uuid4(),uuid4();d=SimpleNamespace(id=did,status="draft");s=SimpleNamespace(id=sid,dataset_id=did);db=Db({("CalibrationDataset",did):d,("CalibrationSample",sid):s})
  service.remove_sample(db,SimpleNamespace(),did,sid);self.assertEqual(db.deleted,[s])
  d.status="frozen"
  with self.assertRaises(HTTPException):service.remove_sample(db,SimpleNamespace(),did,sid)
 def test_annotation_revision_preserves_original_by_creating_successor(self):
  # The service's revision path is deliberately append-only; malformed ownership is denied.
  uid,aid=uuid4(),uuid4();old=SimpleNamespace(id=aid,annotator_user_id=uid,sample_id=uuid4(),annotation_round=1,dimension_code="x",unit="%")
  db=Db({("ReferenceAnnotation",aid):old,("CalibrationSample",old.sample_id):None})
  with self.assertRaises(HTTPException):service.revise_annotation(db,SimpleNamespace(id=uid),aid,SimpleNamespace(value=2,unit=None,comment=None))
if __name__=="__main__":unittest.main()
