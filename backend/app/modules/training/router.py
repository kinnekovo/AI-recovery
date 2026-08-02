from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.training import service
from app.modules.training.schema import TodayTrainingRead, TrainingSessionCreate, TrainingSessionRead
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/types")
def training_types():
    return api_success(service.get_training_types())


@router.get("/today")
def today(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    plan = service.get_or_create_today_plan(db, current_user)
    data = TodayTrainingRead(plan_id=plan.id, title=plan.title, status=plan.status.value, items_count=len(plan.items))
    return api_success(data.model_dump(mode="json"))


@router.post("/session")
def create_session(
    payload: TrainingSessionCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    session = service.create_session(db, current_user, payload.type)
    return api_success(TrainingSessionRead.model_validate(session).model_dump(mode="json"))


@router.get("/session/{session_id}")
def get_session(
    session_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    session = service.get_session(db, current_user, session_id)
    return api_success(TrainingSessionRead.model_validate(session).model_dump(mode="json"))
