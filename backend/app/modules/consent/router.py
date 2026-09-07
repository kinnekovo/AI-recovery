from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.consent.schema import ConsentConfirm, ConsentRevoke
from app.modules.consent.service import record_consent, revoke_consent
from app.modules.users.model import User
from app.modules.users.service import require_patient

router = APIRouter(prefix="/consents", tags=["consent"])


@router.post("")
def confirm_consent(
    payload: ConsentConfirm,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    consent = record_consent(db, current_user, payload.agent_id, payload.consent_type, payload.consent_version)
    db.commit()
    return api_success({"id": str(consent.id)})


@router.post("/revoke")
def revoke(
    payload: ConsentRevoke,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    consent = revoke_consent(db, current_user, payload.agent_id, payload.consent_type)
    db.commit()
    return api_success({"id": str(consent.id)})
