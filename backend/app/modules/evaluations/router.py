from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.evaluations import service
from app.modules.evaluations.model import EvaluationMetricCategory
from app.modules.evaluations.schema import AttemptEvaluationBatchCreate, EvaluationMetricRead
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/metrics")
def list_metrics(
    category: EvaluationMetricCategory | None = None,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    metrics = service.list_metrics(db, category)
    data = [EvaluationMetricRead.model_validate(item).model_dump(mode="json") for item in metrics]
    return api_success(data)


@router.get("/attempts/{attempt_id}")
def list_attempt_evaluations(
    attempt_id: UUID,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.list_attempt_evaluations(db, current_user, attempt_id)
    return api_success(result.model_dump(mode="json"))


@router.post("/attempts/{attempt_id}")
def save_attempt_evaluations(
    attempt_id: UUID,
    payload: AttemptEvaluationBatchCreate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    result = service.save_attempt_evaluations(db, current_user, attempt_id, payload)
    return api_success(result.model_dump(mode="json"))
