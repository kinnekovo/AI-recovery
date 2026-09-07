from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agents.model import Agent
from app.modules.consent.model import ConsentRecord, ConsentStatus
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile


CONSENT_VERSION = "mvp-v1"


def record_consent(db: Session, user: User, agent_id, consent_type: str, version: str = CONSENT_VERSION) -> ConsentRecord:
    ensure_owned_agent(db, user, agent_id)
    consent = ConsentRecord(
        user_id=user.id,
        agent_id=agent_id,
        consent_type=consent_type,
        consent_version=version,
        consent_status=ConsentStatus.confirmed,
    )
    db.add(consent)
    db.flush()
    return consent


def revoke_consent(db: Session, user: User, agent_id, consent_type: str) -> ConsentRecord:
    agent = ensure_owned_agent(db, user, agent_id)
    consent = ConsentRecord(
        user_id=user.id,
        agent_id=agent_id,
        consent_type=consent_type,
        consent_version=CONSENT_VERSION,
        consent_status=ConsentStatus.revoked,
    )
    db.add(consent)
    if consent_type == "image":
        agent.image_consent_confirmed = False
    if consent_type == "voice":
        agent.voice_consent_confirmed = False
        agent.voice_external_id = None
    db.flush()
    return consent


def has_active_consent(db: Session, user: User, agent_id, consent_type: str) -> bool:
    latest = db.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.user_id == user.id,
            ConsentRecord.agent_id == agent_id,
            ConsentRecord.consent_type == consent_type,
        )
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
    )
    return is_confirmed_consent(latest)


def require_active_consent(db: Session, user: User, agent_id, consent_type: str) -> None:
    if not has_active_consent(db, user, agent_id, consent_type):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="授权已撤回或未确认，不能继续使用该素材生成内容")


def is_confirmed_consent(consent: ConsentRecord | None) -> bool:
    return bool(consent and consent.consent_status == ConsentStatus.confirmed)


def ensure_owned_agent(db: Session, user: User, agent_id) -> Agent:
    profile = get_patient_profile(db, user)
    agent = db.get(Agent, agent_id)
    if not agent or agent.patient_profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    return agent
