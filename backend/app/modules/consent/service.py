from sqlalchemy.orm import Session

from app.modules.consent.model import ConsentRecord
from app.modules.users.model import User


def record_consent(db: Session, user: User, agent_id, consent_type: str, version: str = "mvp-v1") -> ConsentRecord:
    consent = ConsentRecord(
        user_id=user.id,
        agent_id=agent_id,
        consent_type=consent_type,
        consent_version=version,
    )
    db.add(consent)
    db.flush()
    return consent
