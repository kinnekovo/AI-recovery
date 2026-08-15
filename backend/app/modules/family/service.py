from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.family.schema import FamilyBoundPatientRead
from app.modules.training.schema import FamilyObservationRead
from app.modules.training.service import build_family_observation_for_patient
from app.modules.users.model import FamilyPatientBinding, PatientProfile, User, UserRole


def list_bound_patients(db: Session, family_user: User) -> list[FamilyBoundPatientRead]:
    rows = db.execute(
        select(FamilyPatientBinding, PatientProfile, User)
        .join(PatientProfile, PatientProfile.id == FamilyPatientBinding.patient_profile_id)
        .join(User, User.id == PatientProfile.user_id)
        .where(
            FamilyPatientBinding.family_user_id == family_user.id,
            FamilyPatientBinding.status == "active",
            User.role == UserRole.patient,
        )
        .order_by(FamilyPatientBinding.created_at.asc())
    ).all()
    return [
        FamilyBoundPatientRead(
            binding_id=binding.id,
            patient_user_id=patient.id,
            patient_profile_id=profile.id,
            patient_username=patient.username,
            relationship_label=binding.relationship_label,
            status=binding.status,
            created_at=binding.created_at,
        )
        for binding, profile, patient in rows
    ]


def get_observation_for_family(
    db: Session,
    family_user: User,
    patient_user_id: UUID | None = None,
) -> FamilyObservationRead:
    bindings = list_bound_patients(db, family_user)
    if not bindings:
        return FamilyObservationRead(
            patient_username="暂无绑定患者",
            training_count=0,
            completed_recommended_sessions=0,
            recommendation_headline="暂无训练建议",
            recommendation_source="system",
            trend_summary="请先由管理员或治疗师绑定患者后再查看训练情况。",
            strategy_hint="完成绑定后，这里会显示患者水平、趋势和陪伴建议。",
            therapist_note=None,
            current_level_label="等待绑定",
            progress_label="暂无趋势",
            progress_percent=0,
            level_items=[],
            trend_items=[],
            bound_patients=[item.model_dump(mode="json") for item in bindings],
            selected_patient_user_id=None,
        )
    selected = bindings[0]
    if patient_user_id:
        selected = next((item for item in bindings if item.patient_user_id == patient_user_id), None)
        if not selected:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该患者")
    return build_family_observation_for_patient(
        db,
        selected.patient_user_id,
        bound_patients=[item.model_dump(mode="json") for item in bindings],
    )
