from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.schema import LoginRequest, RegisterRequest, TokenResponse, TokenUser
from app.modules.users.model import PatientProfile, User, UserRole


def register_user(db: Session, payload: RegisterRequest) -> User:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    if payload.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MVP阶段仅开放患者注册")

    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    db.add(PatientProfile(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(str(user.id), {"role": user.role.value})
    return TokenResponse(access_token=token, user=TokenUser(id=user.id, role=user.role))
