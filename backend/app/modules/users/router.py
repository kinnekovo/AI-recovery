from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.users import service
from app.modules.users.model import User
from app.modules.users.schema import MeRead, PatientProfileRead, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def me(current_user: User = Depends(service.get_current_user), db: Session = Depends(get_db)):
    profile = service.get_patient_profile(db, current_user) if current_user.role.value == "patient" else None
    payload = MeRead(
        user=UserRead.model_validate(current_user),
        patient_profile=PatientProfileRead.model_validate(profile) if profile else None,
    )
    return api_success(payload.model_dump(mode="json"))


@router.put("/current-agent/{agent_id}")
def set_current_agent(
    agent_id: UUID,
    current_user: User = Depends(service.require_patient),
    db: Session = Depends(get_db),
):
    profile = service.set_current_agent(db, current_user, agent_id)
    return api_success(PatientProfileRead.model_validate(profile).model_dump(mode="json"))
