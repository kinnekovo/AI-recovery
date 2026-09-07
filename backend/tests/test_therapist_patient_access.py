import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.agents.model import Agent
from app.modules.files.model import FileAsset
from app.modules.therapist.service import (
    create_patient_assignment,
    list_patients,
    require_therapist_patient_access,
    revoke_patient_assignment,
)
from app.modules.users.model import PatientProfile, TherapistPatientAssignment, User, UserRole


class TherapistPatientAccessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        User.__table__.create(self.engine)
        FileAsset.__table__.create(self.engine)
        Agent.__table__.create(self.engine)
        PatientProfile.__table__.create(self.engine)
        TherapistPatientAssignment.__table__.create(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_therapist_only_sees_assigned_patients(self) -> None:
        with self.SessionLocal() as db:
            admin = User(username="admin", password_hash="x", role=UserRole.admin)
            therapist = User(username="therapist", password_hash="x", role=UserRole.therapist)
            patient_a = User(username="patient-a", password_hash="x", role=UserRole.patient)
            patient_b = User(username="patient-b", password_hash="x", role=UserRole.patient)
            db.add_all([admin, therapist, patient_a, patient_b])
            db.commit()
            for item in [admin, therapist, patient_a, patient_b]:
                db.refresh(item)
            profile_a = PatientProfile(user_id=patient_a.id)
            profile_b = PatientProfile(user_id=patient_b.id)
            db.add_all([profile_a, profile_b])
            db.commit()

            with self.assertRaises(HTTPException):
                require_therapist_patient_access(db, therapist, patient_a.id)
            self.assertEqual(list_patients(db, therapist, backfill=False, include_assessment_summary=False), [])

            assignment = create_patient_assignment(db, admin, therapist.id, patient_a.id)
            self.assertEqual(assignment.status, "active")
            allowed_profile = require_therapist_patient_access(db, therapist, patient_a.id)
            self.assertEqual(allowed_profile.user_id, patient_a.id)
            self.assertEqual(
                [item.user_id for item in list_patients(db, therapist, backfill=False, include_assessment_summary=False)],
                [patient_a.id],
            )
            self.assertEqual(
                {item.user_id for item in list_patients(db, admin, backfill=False, include_assessment_summary=False)},
                {patient_a.id, patient_b.id},
            )

            revoked = revoke_patient_assignment(db, admin, assignment.assignment_id)
            self.assertEqual(revoked.status, "revoked")
            with self.assertRaises(HTTPException):
                require_therapist_patient_access(db, therapist, patient_a.id)
            self.assertEqual(list_patients(db, therapist, backfill=False, include_assessment_summary=False), [])

    def test_only_admin_can_manage_patient_assignments(self) -> None:
        with self.SessionLocal() as db:
            therapist = User(username="therapist", password_hash="x", role=UserRole.therapist)
            patient = User(username="patient", password_hash="x", role=UserRole.patient)
            db.add_all([therapist, patient])
            db.commit()
            db.refresh(therapist)
            db.refresh(patient)
            db.add(PatientProfile(user_id=patient.id))
            db.commit()

            with self.assertRaises(HTTPException):
                create_patient_assignment(db, therapist, therapist.id, patient.id)


if __name__ == "__main__":
    unittest.main()
