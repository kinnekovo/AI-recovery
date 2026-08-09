from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.assessment import service
from app.modules.assessment.model import AssessmentType
from app.modules.assessment.schema import AssessmentCreate
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post("")
def create_assessment(
    payload: AssessmentCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.create_assessment(db, current_user, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/history")
def history(
    assessment_type: AssessmentType | None = None,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.list_history(db, current_user, assessment_type)
    return api_success([item.model_dump(mode="json") for item in result])


@router.get("/compare")
def compare(
    baseline_id: UUID | None = None,
    current_id: UUID | None = None,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.compare_assessments(db, current_user, baseline_id, current_id)
    return api_success(result.model_dump(mode="json"))
