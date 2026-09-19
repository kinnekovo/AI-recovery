from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.response import api_success
from app.database.session import get_db
from app.modules.profile_v2 import service
from app.modules.profile_v2.schema import ProfileSnapshotRead
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile, require_patient

router = APIRouter(prefix="/patient", tags=["profile-v2"])

@router.get("/profile")
def my_profile(current_user: User=Depends(require_patient), db: Session=Depends(get_db)):
    profile=get_patient_profile(db,current_user); snapshot=service.get_latest_profile(db,profile.id)
    if not snapshot: return api_success({"status":"insufficient","freshness":"building","dimensions":[],"limitations":["尚未生成证据画像。"]})
    # Patient projection deliberately excludes raw values, provider metadata and evidence links.
    return api_success({"snapshot_id":str(snapshot.id),"status":snapshot.status,"freshness":"fresh","dimensions":[{"code":d["code"],"status":d["status"],"trend":d["trend"],"evidence_sufficiency":d["evidence_sufficiency"]} for d in snapshot.payload.get("dimensions",[])],"limitations":snapshot.payload.get("limitations",[])})
