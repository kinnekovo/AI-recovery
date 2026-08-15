from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.family import service
from app.modules.users.model import User
from app.modules.users.service import require_family

router = APIRouter(prefix="/family", tags=["family"])


@router.get("/observation")
def observation(
    patient_user_id: UUID | None = None,
    current_user: User = Depends(require_family),
    db: Session = Depends(get_db),
):
    result = service.get_observation_for_family(db, current_user, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients")
def patients(
    current_user: User = Depends(require_family),
    db: Session = Depends(get_db),
):
    result = service.list_bound_patients(db, current_user)
    return api_success([item.model_dump(mode="json") for item in result])
