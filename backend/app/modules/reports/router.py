from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.reports.service import latest_report
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/latest")
def latest(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(latest_report(db, current_user).model_dump(mode="json"))
