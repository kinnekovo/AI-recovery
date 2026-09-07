import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.agents.model import Agent
from app.modules.files.model import FileAsset, FileType
from app.modules.files.service import can_access_patient_profile_file, get_accessible_file
from app.modules.users.model import FamilyPatientBinding, PatientProfile, TherapistPatientAssignment, User, UserRole


class FileAccessPermissionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        User.__table__.create(self.engine)
        FileAsset.__table__.create(self.engine)
        Agent.__table__.create(self.engine)
        PatientProfile.__table__.create(self.engine)
        FamilyPatientBinding.__table__.create(self.engine)
        TherapistPatientAssignment.__table__.create(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_avatar_image_follows_patient_relationship_permissions(self) -> None:
        with self.SessionLocal() as db:
            patient, therapist, family, stranger = self.create_users(db)
            profile = self.create_profile(db, patient)
            image = self.create_file(db, patient, FileType.agent_image)
            db.add(Agent(patient_profile_id=profile.id, name="coach", relationship="康复教练", avatar_file_id=image.id))
            db.add(TherapistPatientAssignment(therapist_user_id=therapist.id, patient_profile_id=profile.id, status="active"))
            db.add(FamilyPatientBinding(family_user_id=family.id, patient_profile_id=profile.id, status="active"))
            db.commit()

            self.assertEqual(get_accessible_file(db, therapist, image.id).id, image.id)
            self.assertEqual(get_accessible_file(db, family, image.id).id, image.id)
            with self.assertRaises(HTTPException):
                get_accessible_file(db, stranger, image.id)

    def test_voice_sample_and_generated_audio_are_owner_or_admin_only(self) -> None:
        with self.SessionLocal() as db:
            patient, therapist, family, _stranger = self.create_users(db)
            admin = User(username="admin", password_hash="x", role=UserRole.admin)
            db.add(admin)
            db.commit()
            db.refresh(admin)
            profile = self.create_profile(db, patient)
            db.add(TherapistPatientAssignment(therapist_user_id=therapist.id, patient_profile_id=profile.id, status="active"))
            db.add(FamilyPatientBinding(family_user_id=family.id, patient_profile_id=profile.id, status="active"))
            voice_sample = self.create_file(db, patient, FileType.voice_sample)
            generated_audio = self.create_file(db, patient, FileType.generated_audio)

            self.assertEqual(get_accessible_file(db, patient, voice_sample.id).id, voice_sample.id)
            self.assertEqual(get_accessible_file(db, admin, voice_sample.id).id, voice_sample.id)
            for user in [therapist, family]:
                with self.assertRaises(HTTPException):
                    get_accessible_file(db, user, voice_sample.id)
                with self.assertRaises(HTTPException):
                    get_accessible_file(db, user, generated_audio.id)

    def test_revoked_patient_relationship_loses_file_access(self) -> None:
        with self.SessionLocal() as db:
            patient, therapist, family, _stranger = self.create_users(db)
            profile = self.create_profile(db, patient)
            db.add(TherapistPatientAssignment(therapist_user_id=therapist.id, patient_profile_id=profile.id, status="revoked"))
            db.add(FamilyPatientBinding(family_user_id=family.id, patient_profile_id=profile.id, status="revoked"))
            db.commit()

            self.assertFalse(can_access_patient_profile_file(db, therapist, profile.id))
            self.assertFalse(can_access_patient_profile_file(db, family, profile.id))

    def create_users(self, db):
        patient = User(username="patient", password_hash="x", role=UserRole.patient)
        therapist = User(username="therapist", password_hash="x", role=UserRole.therapist)
        family = User(username="family", password_hash="x", role=UserRole.family)
        stranger = User(username="stranger", password_hash="x", role=UserRole.therapist)
        db.add_all([patient, therapist, family, stranger])
        db.commit()
        for item in [patient, therapist, family, stranger]:
            db.refresh(item)
        return patient, therapist, family, stranger

    def create_profile(self, db, patient):
        profile = PatientProfile(user_id=patient.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def create_file(self, db, owner, file_type):
        asset = FileAsset(
            owner_user_id=owner.id,
            file_type=file_type,
            original_name=f"{file_type.value}.bin",
            storage_path=f"/tmp/{file_type.value}.bin",
            mime_type="application/octet-stream",
            size_bytes=1,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset


if __name__ == "__main__":
    unittest.main()
