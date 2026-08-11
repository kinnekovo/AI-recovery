from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.profiles.service import get_my_ability_profile
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/ability")
def ability(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    result = get_my_ability_profile(db, current_user)
    return api_success(result.model_dump(mode="json"))
