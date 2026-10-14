from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.review_workflow import service
from app.modules.evaluation_runs import functional_communication_v3, repeat_v3
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate
from app.modules.evaluation_runs.service import get_run, get_run_for_professional
from app.modules.users.model import User
from app.modules.users.service import require_therapist


router = APIRouter(prefix="/v2/therapist", tags=["therapist-review-workflow"])


class AudioOpenedPayload(BaseModel):
    file_id: UUID


@router.get("/review-queue")
def review_queue(
    status: str | None = None,
    type: str | None = None,
    priority: str | None = None,
    patient: str | None = None,
    assigned_to: str = Query(default="all", pattern="^(me|unassigned|all)$"),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    actor: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    statuses = [value.strip() for value in status.split(",") if value.strip()] if status else None
    return api_success(service.review_queue(db, actor, statuses=statuses, item_type=type, priority=priority, patient=patient, assigned_to=assigned_to, cursor=cursor, limit=limit))


@router.get("/attention-items/{item_id}/review-bundle")
def review_bundle(item_id: UUID, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.review_bundle(db, actor, item_id))


@router.post("/attention-items/{item_id}/begin-review")
def begin_review(item_id: UUID, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.begin_review(db, actor, item_id))


@router.post("/attention-items/{item_id}/release")
def release_attention(item_id: UUID, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.release_attention(db, actor, item_id))


@router.post("/attention-items/{item_id}/wait-for-information")
def wait_for_information(item_id: UUID, payload: dict, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    reason = str(payload.get("reason") or "insufficient_evidence")
    note = str(payload.get("note") or "").strip() or None
    return api_success(service.mark_waiting_information(db, actor, item_id, reason, note))


@router.post("/attention-items/{item_id}/audio-opened")
def audio_opened(item_id: UUID, payload: AudioOpenedPayload, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.mark_audio_opened(db, actor, item_id, payload.file_id))


@router.post("/attention-items/{item_id}/evaluation-runs/{run_id}/reviews")
def submit_attention_evaluation_review(item_id: UUID, run_id: UUID, payload: EvaluationReviewRevisionCreate, actor: User = Depends(require_therapist), db: Session = Depends(get_db)):
    attention = service.get_attention_for_actor(db, actor, item_id, lock=True)
    if attention.status in {"resolved", "dismissed", "waiting_plan_publish"}:
        raise HTTPException(status_code=409, detail="当前待办状态不接受评估修订")
    bundle = service.review_bundle(db, actor, item_id)
    if all(run["id"] != str(run_id) for run in bundle["evaluation_runs"]):
        raise HTTPException(status_code=409, detail="该评估运行不属于当前待办的证据")
    current = get_run(db, run_id)
    handler = {"repeat": repeat_v3.review_or_recompute, "functional_communication": functional_communication_v3.review_or_recompute}.get(current.domain)
    if not handler:
        raise HTTPException(status_code=409, detail="该评估类型暂不支持治疗师复核")
    revised_run, revision = handler(db, actor, run_id, payload)
    previous = attention.status
    attention.primary_evaluation_run_id = revised_run.id
    if attention.status in {"open", "acknowledged", "waiting_information"}:
        attention.status = "in_review"
        attention.waiting_reason = None
    attention.assigned_to_user_id = attention.assigned_to_user_id or actor.id
    attention.status_updated_at = service.utc_now()
    service.record_event(db, attention, f"evaluation_review_{payload.review_action}", actor=actor, from_status=previous, to_status=attention.status, note=payload.reason, related_refs={"evaluation_run_id": str(run_id), "adopted_run_id": str(revised_run.id), "revision_id": str(revision.id) if revision else None})
    db.commit()
    return api_success({"run": get_run_for_professional(db, actor, revised_run.id).model_dump(mode="json"), "revision_id": str(revision.id) if revision else None})
