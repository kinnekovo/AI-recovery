from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.training.service import get_family_observation
from app.modules.users.model import User
from app.modules.users.service import require_family

router = APIRouter(prefix="/family", tags=["family"])


@router.get("/observation")
def observation(
    current_user: User = Depends(require_family),
    db: Session = Depends(get_db),
):
    result = get_family_observation(db)
    return api_success(result.model_dump(mode="json"))
