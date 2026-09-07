import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.agents.model import Agent
from app.modules.family.service import family_binding_statuses, list_bound_patients, list_family_bindings, update_binding_status
from app.modules.files.model import FileAsset
from app.modules.users.model import FamilyPatientBinding, PatientProfile, User, UserRole


class FamilyBindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        User.__table__.create(self.engine)
        FileAsset.__table__.create(self.engine)
        Agent.__table__.create(self.engine)
        PatientProfile.__table__.create(self.engine)
        FamilyPatientBinding.__table__.create(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_observation_only_allows_active_bindings(self) -> None:
        self.assertEqual(family_binding_statuses(active_only=True), ["active"])

    def test_binding_list_shows_pending_and_active(self) -> None:
        self.assertEqual(family_binding_statuses(active_only=False), ["pending", "active"])

    def test_pending_binding_can_be_confirmed_and_revoked(self) -> None:
        with self.SessionLocal() as db:
            family = User(username="family", password_hash="x", role=UserRole.family)
            patient_user = User(username="patient", password_hash="x", role=UserRole.patient)
            db.add_all([family, patient_user])
            db.commit()
            db.refresh(family)
            db.refresh(patient_user)
            profile = PatientProfile(user_id=patient_user.id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
            binding = FamilyPatientBinding(
                family_user_id=family.id,
                patient_profile_id=profile.id,
                relationship_label="母亲",
                status="pending",
            )
            db.add(binding)
            db.commit()
            db.refresh(binding)

            self.assertEqual([item.status for item in list_family_bindings(db, family)], ["pending"])
            self.assertEqual(list_bound_patients(db, family), [])

            confirmed = update_binding_status(db, family, binding.id, "active")
            self.assertEqual(confirmed.status, "active")
            self.assertEqual([item.status for item in list_bound_patients(db, family)], ["active"])

            revoked = update_binding_status(db, family, binding.id, "revoked")
            self.assertEqual(revoked.status, "revoked")
            self.assertEqual(list_family_bindings(db, family), [])
            self.assertEqual(list_bound_patients(db, family), [])

            with self.assertRaises(HTTPException):
                update_binding_status(db, family, binding.id, "active")


if __name__ == "__main__":
    unittest.main()
