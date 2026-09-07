import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password
from app.database.session import SessionLocal
from app.modules.training.service import ensure_seed_tasks
from app.modules.users.model import (
    FamilyPatientBinding,
    PatientProfile,
    TherapistPatientAssignment,
    User,
    UserRole,
    UserStatus,
)


DEFAULT_PASSWORD = "Trial2026!"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize trial users and relationships.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password used for all trial accounts.")
    parser.add_argument("--patient-count", type=int, default=3, help="Number of patient accounts to create.")
    parser.add_argument("--family-count", type=int, default=3, help="Number of family accounts to create.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned accounts without writing the database.")
    args = parser.parse_args()

    if args.patient_count < 1:
        raise SystemExit("--patient-count must be at least 1")
    if args.family_count < 0:
        raise SystemExit("--family-count must be zero or greater")
    if args.dry_run:
        print(json.dumps(planned_payload(args.password, args.patient_count, args.family_count), ensure_ascii=False, indent=2))
        return 0

    with SessionLocal() as db:
        ensure_seed_tasks(db)
        admin = upsert_user(db, "trial_admin", args.password, UserRole.admin)
        therapist = upsert_user(db, "trial_therapist_01", args.password, UserRole.therapist)
        patients = [
            upsert_user(db, f"trial_patient_{index:02d}", args.password, UserRole.patient)
            for index in range(1, args.patient_count + 1)
        ]
        families = [
            upsert_user(db, f"trial_family_{index:02d}", args.password, UserRole.family)
            for index in range(1, args.family_count + 1)
        ]
        patient_profiles = [ensure_patient_profile(db, patient) for patient in patients]
        assignments = [
            upsert_therapist_assignment(db, therapist, profile)
            for profile in patient_profiles
        ]
        bindings = [
            upsert_family_binding(db, family, patient_profiles[index], status="pending")
            for index, family in enumerate(families[: len(patient_profiles)])
        ]
        db.commit()
        payload = {
            "password": args.password,
            "accounts": {
                "admin": admin.username,
                "therapist": therapist.username,
                "patients": [patient.username for patient in patients],
                "families": [family.username for family in families],
            },
            "therapist_assignments": len(assignments),
            "pending_family_bindings": len(bindings),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def planned_payload(password: str, patient_count: int, family_count: int) -> dict:
    return {
        "dry_run": True,
        "password": password,
        "accounts": {
            "admin": "trial_admin",
            "therapist": "trial_therapist_01",
            "patients": [f"trial_patient_{index:02d}" for index in range(1, patient_count + 1)],
            "families": [f"trial_family_{index:02d}" for index in range(1, family_count + 1)],
        },
        "therapist_assignments": patient_count,
        "pending_family_bindings": min(patient_count, family_count),
    }


def upsert_user(db, username: str, password: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.username == username))
    password_hash = hash_password(password)
    if user:
        user.password_hash = password_hash
        user.role = role
        user.status = UserStatus.active
        db.flush()
        return user
    user = User(username=username, password_hash=password_hash, role=role, status=UserStatus.active)
    db.add(user)
    db.flush()
    return user


def ensure_patient_profile(db, patient: User) -> PatientProfile:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id))
    if profile:
        return profile
    profile = PatientProfile(user_id=patient.id)
    db.add(profile)
    db.flush()
    return profile


def upsert_therapist_assignment(db, therapist: User, profile: PatientProfile) -> TherapistPatientAssignment:
    assignment = db.scalar(
        select(TherapistPatientAssignment).where(
            TherapistPatientAssignment.therapist_user_id == therapist.id,
            TherapistPatientAssignment.patient_profile_id == profile.id,
        )
    )
    if assignment:
        assignment.status = "active"
        db.flush()
        return assignment
    assignment = TherapistPatientAssignment(
        therapist_user_id=therapist.id,
        patient_profile_id=profile.id,
        status="active",
    )
    db.add(assignment)
    db.flush()
    return assignment


def upsert_family_binding(db, family: User, profile: PatientProfile, status: str) -> FamilyPatientBinding:
    binding = db.scalar(
        select(FamilyPatientBinding).where(
            FamilyPatientBinding.family_user_id == family.id,
            FamilyPatientBinding.patient_profile_id == profile.id,
        )
    )
    if binding:
        binding.status = status
        db.flush()
        return binding
    binding = FamilyPatientBinding(
        family_user_id=family.id,
        patient_profile_id=profile.id,
        relationship_label="家属",
        status=status,
    )
    db.add(binding)
    db.flush()
    return binding


if __name__ == "__main__":
    raise SystemExit(main())
