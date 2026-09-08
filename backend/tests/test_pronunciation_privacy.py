from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.database.base import import_models
from app.modules.pronunciation.service import _original_value, get_patient_attempt_pronunciation

import_models()


class _FakeDb:
    def __init__(self, value):
        self.value = value

    def scalar(self, _statement):
        return self.value


class PronunciationPrivacyTest(unittest.TestCase):
    def test_patient_result_excludes_therapist_audit_records(self) -> None:
        analysis = SimpleNamespace(
            attempt_id=uuid4(),
            status="completed",
            overall_accuracy=88.0,
            fluency=0.8,
            completion=0.9,
            intelligibility_proxy=85.0,
            confidence=0.9,
            coverage=1.0,
            prosody_metrics={"status": "completed"},
            error_code=None,
            error_message=None,
            segments=[],
            revisions=[SimpleNamespace(reason="治疗师私有备注")],
            intelligibility_reviews=[SimpleNamespace(listener_transcript="私有听辨转写")],
            created_at=datetime.now(timezone.utc),
        )

        result = get_patient_attempt_pronunciation(_FakeDb(analysis), analysis.attempt_id)

        payload = result.model_dump()
        self.assertNotIn("revisions", payload)
        self.assertNotIn("intelligibility_reviews", payload)
        self.assertNotIn("治疗师私有备注", str(payload))
        self.assertNotIn("私有听辨转写", str(payload))

    def test_revision_rejects_non_metric_attribute(self) -> None:
        segment = SimpleNamespace(id=uuid4(), analysis_id=uuid4(), accuracy=80.0)
        with self.assertRaises(HTTPException) as raised:
            _original_value(SimpleNamespace(), segment, "id")
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
