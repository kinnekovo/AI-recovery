import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database.session import get_db
from app.main import create_app
from app.modules.agents.model import Agent
from app.modules.evaluation_runs.model import EvaluationDimensionResult, EvaluationReviewRevision, EvaluationRun
from app.modules.evaluation_runs.schema import (
    EvaluationDimensionResultCreate,
    EvaluationReviewRevisionCreate,
    EvaluationRunCreate,
    InputProvenanceSnapshot,
    QualityGateSnapshot,
)
from app.modules.evaluation_runs.service import (
    adopt_candidate_run,
    append_review_revision,
    create_candidate_run,
    get_run,
    get_run_for_professional,
    list_source_versions,
)
from app.modules.files.model import FileAsset
from app.modules.scoring.model import AttemptScore  # noqa: F401 - resolves Attempt relationship for this isolated ORM test
from app.modules.users.model import PatientProfile, TherapistPatientAssignment, User, UserRole


class EvaluationRunsV3FoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for table in [
            User.__table__,
            FileAsset.__table__,
            Agent.__table__,
            PatientProfile.__table__,
            TherapistPatientAssignment.__table__,
            EvaluationRun.__table__,
            EvaluationDimensionResult.__table__,
            EvaluationReviewRevision.__table__,
        ]:
            table.create(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.SessionLocal() as db:
            self.patient_a = User(username="run-patient-a", password_hash="x", role=UserRole.patient)
            self.patient_b = User(username="run-patient-b", password_hash="x", role=UserRole.patient)
            self.therapist = User(username="run-therapist", password_hash="x", role=UserRole.therapist)
            self.stranger = User(username="run-stranger", password_hash="x", role=UserRole.therapist)
            db.add_all([self.patient_a, self.patient_b, self.therapist, self.stranger])
            db.commit()
            self.profile_a = PatientProfile(user_id=self.patient_a.id)
            self.profile_b = PatientProfile(user_id=self.patient_b.id)
            db.add_all([self.profile_a, self.profile_b])
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def payload(self, *, profile_id=None, source_id=None, domain="repeat", result_status="formal", dimensions=None):
        return EvaluationRunCreate(
            patient_profile_id=profile_id or self.profile_a.id,
            domain=domain,
            source_type="assessment_session",
            source_id=source_id or uuid4(),
            algorithm_version="canonical-foundation-test-v1",
            config_snapshot={"test": True},
            input_provenance=InputProvenanceSnapshot(source_snapshot={"assessment": "immutable-copy"}),
            quality_gate=QualityGateSnapshot(eligible=result_status == "formal", reasons=[] if result_status == "formal" else ["needs_review"]),
            result_status=result_status,
            profile_eligibility=result_status == "formal",
            dimensions=dimensions or [],
        )

    def create(self, db, payload):
        with patch("app.modules.evaluation_runs.service.source_patient_profile_id", return_value=payload.patient_profile_id):
            return create_candidate_run(db, payload)

    def test_all_domains_and_result_statuses_are_stored(self) -> None:
        with self.SessionLocal() as db:
            domains = ["repeat", "functional_communication", "clinical_stage"]
            statuses = ["formal", "provisional", "review_required", "unscorable"]
            runs = [self.create(db, self.payload(domain=domain, result_status=status)) for domain, status in zip(domains + ["repeat"], statuses)]
            self.assertEqual([item.domain for item in runs], domains + ["repeat"])
            self.assertEqual([item.result_status for item in runs], statuses)
            self.assertTrue(all(item.adoption_status == "candidate" for item in runs))

    def test_zero_is_measured_and_not_observed_remains_null(self) -> None:
        dimensions = [
            EvaluationDimensionResultCreate(dimension_code="event_count", value=0, unit="count/task", status="measured"),
            EvaluationDimensionResultCreate(dimension_code="repair_ability", status="not_observed"),
        ]
        with self.SessionLocal() as db:
            run = self.create(db, self.payload(dimensions=dimensions))
            values = {item.dimension_code: item.value for item in get_run(db, run.id).dimension_results}
            self.assertEqual(values["event_count"], 0.0)
            self.assertIsNone(values["repair_ability"])
        with self.assertRaises(ValueError):
            EvaluationDimensionResultCreate(dimension_code="bad", value=1, status="not_observed")

    def test_adoption_supersedes_old_run_and_is_retry_safe(self) -> None:
        source_id = uuid4()
        with self.SessionLocal() as db:
            old = self.create(db, self.payload(source_id=source_id))
            new = self.create(db, self.payload(source_id=source_id))
            self.assertEqual(adopt_candidate_run(db, old.id).adoption_status, "adopted")
            self.assertEqual(adopt_candidate_run(db, old.id).id, old.id)
            adopted_new = adopt_candidate_run(db, new.id)
            self.assertEqual(adopted_new.adoption_status, "adopted")
            self.assertEqual(adopted_new.supersedes_run_id, old.id)
            self.assertEqual(get_run(db, old.id).adoption_status, "superseded")
            adopted = [item for item in list_source_versions(db, "assessment_session", source_id, "repeat") if item.adoption_status == "adopted"]
            self.assertEqual([item.id for item in adopted], [new.id])

    def test_review_revision_is_append_only_and_preserves_automatic_value(self) -> None:
        dimension = EvaluationDimensionResultCreate(dimension_code="content_reproduction", value=72, unit="%", status="measured")
        with self.SessionLocal() as db:
            run = self.create(db, self.payload(dimensions=[dimension]))
            original = get_run(db, run.id).dimension_results[0]
            revision = append_review_revision(
                db,
                run.id,
                EvaluationReviewRevisionCreate(
                    dimension_result_id=original.id,
                    review_action="corrected",
                    automatic_value_snapshot={"value": 72},
                    revised_value_snapshot={"value": 80},
                    reason="听音复核后修订",
                ),
            )
            self.assertEqual(revision.automatic_value_snapshot["value"], 72)
            self.assertEqual(get_run(db, run.id).dimension_results[0].value, 72)
            self.assertEqual(len(get_run(db, run.id).review_revisions), 1)

    def test_cross_patient_source_is_rejected(self) -> None:
        with self.SessionLocal() as db:
            payload = self.payload(profile_id=self.profile_a.id)
            with patch("app.modules.evaluation_runs.service.source_patient_profile_id", return_value=self.profile_b.id):
                with self.assertRaises(HTTPException) as error:
                    create_candidate_run(db, payload)
            self.assertEqual(error.exception.status_code, 409)

    def test_professional_read_requires_active_assignment_and_read_does_not_follow_mutable_source(self) -> None:
        with self.SessionLocal() as db:
            run = self.create(db, self.payload())
            with self.assertRaises(HTTPException) as error:
                get_run_for_professional(db, self.stranger, run.id)
            self.assertEqual(error.exception.status_code, 403)
            db.add(TherapistPatientAssignment(therapist_user_id=self.therapist.id, patient_profile_id=self.profile_a.id, status="active"))
            db.commit()
            read = get_run_for_professional(db, self.therapist, run.id)
            self.assertEqual(read.input_provenance.source_snapshot["assessment"], "immutable-copy")
            self.assertEqual(read.source_id, run.source_id)

    def test_professional_read_api_rejects_unassigned_therapist(self) -> None:
        with self.SessionLocal() as db:
            run = self.create(db, self.payload())
            app = create_app()

            def override_db():
                yield db

            app.dependency_overrides[get_db] = override_db
            client = TestClient(app)
            stranger_token = create_access_token(str(self.stranger.id))
            denied = client.get(f"/api/evaluation-runs/{run.id}", headers={"Authorization": f"Bearer {stranger_token}"})
            self.assertEqual(denied.status_code, 403)

            db.add(TherapistPatientAssignment(therapist_user_id=self.therapist.id, patient_profile_id=self.profile_a.id, status="active"))
            db.commit()
            therapist_token = create_access_token(str(self.therapist.id))
            allowed = client.get(f"/api/evaluation-runs/{run.id}", headers={"Authorization": f"Bearer {therapist_token}"})
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.json()["data"]["id"], str(run.id))


if __name__ == "__main__":
    unittest.main()
