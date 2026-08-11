from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.modules.users.model import PatientProfile, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效登录凭证") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def require_patient(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅患者用户可访问")
    return user


def require_family(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.family:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅家属用户可访问")
    return user


def require_therapist(user: User = Depends(get_current_user)) -> User:
    if user.role not in {UserRole.therapist, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅治疗师或管理员可访问")
    return user


def get_patient_profile(db: Session, user: User) -> PatientProfile:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    return profile


def set_current_agent(db: Session, user: User, agent_id: UUID) -> PatientProfile:
    from app.modules.agents.model import Agent

    profile = get_patient_profile(db, user)
    agent = db.get(Agent, agent_id)
    if not agent or agent.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    profile.current_agent_id = agent.id
    profile.onboarding_status = "ready"
    db.commit()
    db.refresh(profile)
    return profile
