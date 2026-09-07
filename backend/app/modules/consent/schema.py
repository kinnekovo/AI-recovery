from uuid import UUID

from pydantic import BaseModel


class ConsentConfirm(BaseModel):
    agent_id: UUID
    consent_type: str
    consent_version: str = "mvp-v1"


class ConsentRevoke(BaseModel):
    agent_id: UUID
    consent_type: str
