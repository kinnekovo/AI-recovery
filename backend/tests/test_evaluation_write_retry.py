import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modules.evaluation_runs.model import EvaluationWriteFailure
from app.modules.evaluation_runs.service import record_evaluation_write_failure, resolve_evaluation_write_failure


class EvaluationWriteRetryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        EvaluationWriteFailure.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self):
        self.engine.dispose()

    def test_failure_is_persisted_and_success_resolves_it(self):
        source_id = uuid4()
        with self.Session() as db:
            first = record_evaluation_write_failure(db, source_type="dialogue_session", source_id=source_id,
                domain="functional_communication", algorithm_version="functional-communication-eval-v3.0", failure_stage="shadow_write")
            again = record_evaluation_write_failure(db, source_type="dialogue_session", source_id=source_id,
                domain="functional_communication", algorithm_version="functional-communication-eval-v3.0", failure_stage="shadow_write")
            self.assertEqual(first.id, again.id)
            self.assertTrue(again.retry_required)
            self.assertEqual(again.retry_count, 2)
            run = SimpleNamespace(id=uuid4())
            resolve_evaluation_write_failure(db, source_type="dialogue_session", source_id=source_id,
                domain="functional_communication", algorithm_version="functional-communication-eval-v3.0", run=run)
            self.assertFalse(again.retry_required)
            self.assertEqual(again.resolved_run_id, run.id)


if __name__ == "__main__":
    unittest.main()
