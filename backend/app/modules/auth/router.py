from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.auth import service
from app.modules.auth.schema import LoginRequest, RegisterRequest
from app.modules.users.schema import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = service.register_user(db, payload)
    return api_success({"user": UserRead.model_validate(user).model_dump(mode="json")})


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token = service.authenticate_user(db, payload)
    return api_success(token.model_dump(mode="json"))
