from collections import Counter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.observability import log_event
from app.database.base import utc_now
from app.modules.attempts.model import Attempt
from app.modules.evaluation_runs.model import EvaluationRun
from app.modules.evaluation_runs.schema import EvaluationRunRead
from app.modules.evaluation_runs.service import get_run_for_professional
from app.modules.product_v2.model import (
    AttentionItem,
    EvidenceRecord,
    MetricRecord,
    RehabilitationGoal,
    TrainingPlanVersion,
)
from app.modules.review_workflow.model import AttentionItemEvent
from app.modules.scenario_dialogues.model import DialogueSpeaker, ScenarioDialogueSession, ScenarioDialogueTurn
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.therapist.service import require_therapist_patient_access
from app.modules.training.model import SessionTask, TaskTemplate, TrainingSession
from app.modules.users.model import PatientProfile, TherapistPatientAssignment, User, UserRole


OPEN_STATUSES = ("open", "acknowledged", "in_review", "waiting_information", "waiting_plan_publish")
PRIORITY_ORDER = case(
    (AttentionItem.priority == "high", 0),
    (AttentionItem.priority == "normal", 1),
    else_=2,
)
STATUS_ORDER = case(
    (AttentionItem.status == "open", 0),
    (AttentionItem.status == "acknowledged", 1),
    (AttentionItem.status == "in_review", 2),
    (AttentionItem.status == "waiting_information", 3),
    else_=4,
)


def record_event(
    db: Session,
    item: AttentionItem,
    event_type: str,
    *,
    actor: User | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    related_refs: dict | None = None,
    commit: bool = False,
) -> AttentionItemEvent:
    row = AttentionItemEvent(
        attention_item_id=item.id,
        actor_user_id=actor.id if actor else None,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
        related_refs=related_refs or {},
        created_at=utc_now(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _patient_label(db: Session, profile_id: UUID) -> tuple[PatientProfile, User]:
    profile = db.get(PatientProfile, profile_id)
    patient = db.get(User, profile.user_id) if profile else None
    if not profile or not patient:
        raise HTTPException(status_code=404, detail="患者档案不存在")
    return profile, patient


def _attention_payload(db: Session, row: AttentionItem) -> dict:
    profile, patient = _patient_label(db, row.patient_profile_id)
    owner = db.get(User, row.assigned_to_user_id) if row.assigned_to_user_id else None
    refs = row.source_refs if isinstance(row.source_refs, list) else []
    return {
        "id": str(row.id),
        "patient_user_id": str(patient.id),
        "patient_profile_id": str(profile.id),
        "patient": patient.username,
        "type": row.item_type,
        "trigger_code": row.trigger_code,
        "trigger_facts": row.trigger_facts or {},
        "source_refs": refs,
        "evidence_ids": [str(value) for value in (row.evidence_ids or [])],
        "priority": row.priority,
        "summary": row.summary,
        "status": row.status,
        "assigned_to_user_id": str(row.assigned_to_user_id) if row.assigned_to_user_id else None,
        "assigned_to": owner.username if owner else None,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "created_at": row.created_at.isoformat(),
        "status_updated_at": row.status_updated_at.isoformat() if row.status_updated_at else row.created_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolution_code": row.resolution_code,
        "resolution_note": row.resolution_note,
        "waiting_reason": row.waiting_reason,
        "primary_evaluation_run_id": str(row.primary_evaluation_run_id) if row.primary_evaluation_run_id else None,
        "primary_stage_review_id": str(row.primary_stage_review_id) if row.primary_stage_review_id else None,
        "evidence_count": len(refs) + len(row.evidence_ids or []),
        "next_step": _next_step(row),
    }


def _next_step(item: AttentionItem) -> str:
    return {
        "open": "需要接手并查看证据",
        "acknowledged": "继续复核证据",
        "in_review": "完成证据复核或形成阶段决定",
        "waiting_information": "等待补充录音或材料",
        "waiting_plan_publish": "方案草稿待发布",
    }.get(item.status, "查看处理记录")


def review_queue(
    db: Session,
    actor: User,
    *,
    statuses: list[str] | None = None,
    item_type: str | None = None,
    priority: str | None = None,
    patient: str | None = None,
    assigned_to: str = "all",
    cursor: str | None = None,
    limit: int = 20,
) -> dict:
    allowed_statuses = [value for value in (statuses or list(OPEN_STATUSES)) if value in OPEN_STATUSES]
    if not allowed_statuses:
        allowed_statuses = list(OPEN_STATUSES)
    statement = (
        select(AttentionItem)
        .join(PatientProfile, PatientProfile.id == AttentionItem.patient_profile_id)
        .join(User, User.id == PatientProfile.user_id)
        .where(AttentionItem.status.in_(allowed_statuses))
    )
    if actor.role != UserRole.admin:
        assigned_profiles = select(TherapistPatientAssignment.patient_profile_id).where(
            TherapistPatientAssignment.therapist_user_id == actor.id,
            TherapistPatientAssignment.status == "active",
        )
        statement = statement.where(AttentionItem.patient_profile_id.in_(assigned_profiles))
    if item_type:
        statement = statement.where(AttentionItem.item_type == item_type)
    if priority in {"high", "normal", "low"}:
        statement = statement.where(AttentionItem.priority == priority)
    if patient:
        statement = statement.where(User.username.ilike(f"%{patient.strip()}%"))
    if assigned_to == "me":
        statement = statement.where(AttentionItem.assigned_to_user_id == actor.id)
    elif assigned_to == "unassigned":
        statement = statement.where(AttentionItem.assigned_to_user_id.is_(None))

    try:
        offset = max(0, int(cursor or 0))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="队列游标格式无效") from exc
    page_size = min(max(limit, 1), 100)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(
        db.scalars(
            statement.order_by(PRIORITY_ORDER, STATUS_ORDER, AttentionItem.created_at.asc(), AttentionItem.id.asc())
            .offset(offset)
            .limit(page_size)
        )
    )
    visible = list(db.scalars(select(AttentionItem).where(AttentionItem.status.in_(OPEN_STATUSES))))
    if actor.role != UserRole.admin:
        visible = [item for item in visible if db.scalar(select(TherapistPatientAssignment.id).where(
            TherapistPatientAssignment.therapist_user_id == actor.id,
            TherapistPatientAssignment.patient_profile_id == item.patient_profile_id,
            TherapistPatientAssignment.status == "active",
        ).limit(1))]
    summary = Counter(item.status for item in visible)
    return {
        "summary": {
            "open": summary["open"],
            "mine": sum(item.assigned_to_user_id == actor.id for item in visible),
            "waiting_information": summary["waiting_information"],
            "waiting_plan_publish": summary["waiting_plan_publish"],
            "total": len(visible),
        },
        "items": [_attention_payload(db, item) for item in rows],
        "next_cursor": str(offset + len(rows)) if offset + len(rows) < total else None,
        "total": total,
    }


def get_attention_for_actor(db: Session, actor: User, item_id: UUID, *, lock: bool = False) -> AttentionItem:
    statement = select(AttentionItem).where(AttentionItem.id == item_id)
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if not item:
        raise HTTPException(status_code=404, detail="待复核事项不存在")
    profile, _ = _patient_label(db, item.patient_profile_id)
    require_therapist_patient_access(db, actor, profile.user_id)
    return item


def begin_review(db: Session, actor: User, item_id: UUID) -> dict:
    item = get_attention_for_actor(db, actor, item_id, lock=True)
    if item.status in {"resolved", "dismissed"}:
        raise HTTPException(status_code=409, detail="该待办已关闭，复核记录为只读")
    if item.status == "waiting_plan_publish":
        raise HTTPException(status_code=409, detail="该待办正在等待方案发布，请从待发布方案继续处理")
    if item.assigned_to_user_id and item.assigned_to_user_id != actor.id and actor.role != UserRole.admin:
        owner = db.get(User, item.assigned_to_user_id)
        raise HTTPException(status_code=409, detail=f"该待办由 {owner.username if owner else '其他治疗师'} 接手，请联系负责人转交")
    previous = item.status
    item.status = "in_review"
    item.assigned_to_user_id = actor.id
    item.acknowledged_at = item.acknowledged_at or utc_now()
    item.status_updated_at = utc_now()
    item.waiting_reason = None
    record_event(db, item, "review_started", actor=actor, from_status=previous, to_status="in_review")
    db.commit()
    log_event("info", "review_workflow", "attention_review_started", attention_item_id=str(item.id), actor_user_id=str(actor.id))
    return _attention_payload(db, item)


def release_attention(db: Session, actor: User, item_id: UUID) -> dict:
    item = get_attention_for_actor(db, actor, item_id, lock=True)
    if item.assigned_to_user_id != actor.id:
        raise HTTPException(status_code=409, detail="只能释放自己接手的待办")
    if item.status == "in_review":
        raise HTTPException(status_code=409, detail="已开始复核的待办不能释放；请保留负责人或由管理员转交")
    if item.status not in {"acknowledged", "open"}:
        raise HTTPException(status_code=409, detail="当前状态不能释放")
    previous = item.status
    item.assigned_to_user_id = None
    item.acknowledged_at = None
    item.status = "open"
    item.status_updated_at = utc_now()
    record_event(db, item, "released", actor=actor, from_status=previous, to_status="open")
    db.commit()
    return _attention_payload(db, item)


def mark_waiting_information(db: Session, actor: User, item_id: UUID, reason: str, note: str | None = None) -> dict:
    item = get_attention_for_actor(db, actor, item_id, lock=True)
    if item.assigned_to_user_id != actor.id and actor.role != UserRole.admin:
        raise HTTPException(status_code=409, detail="请先接手该待办")
    if item.status not in {"acknowledged", "in_review", "waiting_information"}:
        raise HTTPException(status_code=409, detail="当前状态不能转为等待补充")
    previous = item.status
    item.status = "waiting_information"
    item.waiting_reason = reason
    item.status_updated_at = utc_now()
    if note:
        item.resolution_note = note
    record_event(db, item, "waiting_for_information", actor=actor, from_status=previous, to_status=item.status, note=note, related_refs={"reason": reason})
    db.commit()
    return _attention_payload(db, item)


def mark_audio_opened(db: Session, actor: User, item_id: UUID, file_id: UUID) -> dict:
    item = get_attention_for_actor(db, actor, item_id)
    bundle = review_bundle(db, actor, item_id)
    if all(audio["file_id"] != str(file_id) for audio in bundle["audio_assets"]):
        raise HTTPException(status_code=404, detail="该录音不属于当前复核事项")
    record_event(db, item, "review_audio_opened", actor=actor, from_status=item.status, to_status=item.status, related_refs={"file_id": str(file_id)})
    db.commit()
    return {"recorded": True}


def _audio(file_id: UUID | None) -> dict | None:
    if not file_id:
        return None
    return {"file_id": str(file_id), "url": f"/api/files/{file_id}/content"}


def _safe_enum(value) -> str:
    return str(getattr(value, "value", value))


def _source_tasks(db: Session, refs: list) -> tuple[list[SessionTask], list[UUID]]:
    task_ids: list[UUID] = []
    direct_source_ids: list[UUID] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        try:
            entity_id = UUID(str(ref.get("id")))
        except (TypeError, ValueError):
            continue
        kind = str(ref.get("type") or ref.get("source_type") or "")
        direct_source_ids.append(entity_id)
        if kind == "session_task":
            task_ids.append(entity_id)
        elif kind == "attempt":
            attempt = db.get(Attempt, entity_id)
            if attempt:
                task_ids.append(attempt.session_task_id)
        elif kind in {"dialogue_session", "scenario_dialogue"}:
            dialogue = db.get(ScenarioDialogueSession, entity_id)
            if dialogue:
                task_ids.append(dialogue.session_task_id)
        elif kind == "metric":
            metric = db.get(MetricRecord, entity_id)
            if metric and metric.source_type == "attempt":
                attempt = db.get(Attempt, metric.source_id)
                if attempt:
                    task_ids.append(attempt.session_task_id)
            elif metric and metric.source_type == "scenario_dialogue":
                dialogue = db.get(ScenarioDialogueSession, metric.source_id)
                if dialogue:
                    task_ids.append(dialogue.session_task_id)
    tasks = list(
        db.scalars(
            select(SessionTask)
            .options(selectinload(SessionTask.task_template), selectinload(SessionTask.session))
            .where(SessionTask.id.in_(set(task_ids)))
            .order_by(SessionTask.created_at.asc())
        )
    ) if task_ids else []
    return tasks, list(dict.fromkeys(direct_source_ids))


def review_bundle(db: Session, actor: User, item_id: UUID) -> dict:
    item = get_attention_for_actor(db, actor, item_id)
    profile, patient = _patient_label(db, item.patient_profile_id)
    goal = db.scalar(select(RehabilitationGoal).where(RehabilitationGoal.patient_profile_id == profile.id, RehabilitationGoal.status == "active", RehabilitationGoal.is_primary.is_(True)))
    plan = db.scalar(select(TrainingPlanVersion).where(TrainingPlanVersion.patient_profile_id == profile.id, TrainingPlanVersion.status == "active"))
    refs = item.source_refs if isinstance(item.source_refs, list) else []
    tasks, _ = _source_tasks(db, refs)
    attempts: list[dict] = []
    dialogues: list[dict] = []
    source_ids: list[tuple[str, UUID]] = []
    for task in tasks:
        session = task.session
        template = task.task_template
        task_family = _safe_enum(task.exercise_type_snapshot or (template.task_type if template else "unknown"))
        task_data = {
            "id": str(task.id),
            "title": (task.content_snapshot or {}).get("title") or (template.title if template else "训练任务"),
            "instruction": task.instruction_snapshot or (task.content_snapshot or {}).get("instruction") or (template.instruction if template else ""),
            "target": task.target_snapshot or (task.content_snapshot or {}).get("target_text") or (template.target_text if template else ""),
            "type": task_family,
            "created_at": task.created_at.isoformat(),
            "session_id": str(session.id) if session else None,
            "session_date": session.local_session_date.isoformat() if session and session.local_session_date else None,
        }
        attempt_rows = list(db.scalars(select(Attempt).where(Attempt.session_task_id == task.id).order_by(Attempt.attempt_no.asc())))
        for attempt in attempt_rows:
            analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
            attempts.append({
                "id": str(attempt.id),
                "task": task_data,
                "attempt_no": attempt.attempt_no,
                "prompt_level": attempt.prompt_level,
                "status": attempt.terminal_state,
                "technical_validity": attempt.technical_validity,
                "measurement_eligibility": attempt.measurement_eligibility,
                "audio_quality": attempt.audio_quality,
                "audio": _audio(attempt.audio_file_id),
                "transcript": analysis.asr_text if analysis else None,
                "analysis_status": _safe_enum(attempt.analysis_status),
                "created_at": attempt.created_at.isoformat(),
                "duration_ms": attempt.duration_ms,
            })
            source_ids.append(("attempt", attempt.id))
        dialogue = db.scalar(select(ScenarioDialogueSession).where(ScenarioDialogueSession.session_task_id == task.id))
        if dialogue:
            turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id).order_by(ScenarioDialogueTurn.turn_index)))
            dialogues.append({
                "id": str(dialogue.id),
                "task": task_data,
                "status": _safe_enum(dialogue.status),
                "contract_version": dialogue.contract_version,
                "contract": dialogue.contract_snapshot or {},
                "prompt_count": dialogue.prompt_count,
                "turns": [{
                    "id": str(turn.id),
                    "index": turn.turn_index,
                    "speaker": _safe_enum(turn.speaker),
                    "speaker_label": "患者" if turn.speaker == DialogueSpeaker.patient else "陪练",
                    "text": turn.text,
                    "audio": _audio(turn.audio_file_id),
                    "asr_provider": turn.asr_provider,
                    "semantic_evidence": turn.semantic_evidence or {},
                    "dialogue_act": turn.dialogue_act,
                    "created_at": turn.created_at.isoformat(),
                } for turn in turns],
            })
            source_ids.append(("dialogue_session", dialogue.id))

    runs = []
    for source_type, source_id in source_ids:
        rows = list(db.scalars(
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.dimension_results), selectinload(EvaluationRun.review_revisions))
            .where(EvaluationRun.source_type == source_type, EvaluationRun.source_id == source_id)
            .order_by(EvaluationRun.created_at.desc())
        ))
        for run in rows:
            if all(existing["id"] != str(run.id) for existing in runs):
                get_run_for_professional(db, actor, run.id)
                runs.append(EvaluationRunRead.model_validate(run).model_dump(mode="json"))
    if item.primary_evaluation_run_id and all(existing["id"] != str(item.primary_evaluation_run_id) for existing in runs):
        get_run_for_professional(db, actor, item.primary_evaluation_run_id)
        run = db.scalar(select(EvaluationRun).options(selectinload(EvaluationRun.dimension_results), selectinload(EvaluationRun.review_revisions)).where(EvaluationRun.id == item.primary_evaluation_run_id))
        if run:
            runs.insert(0, EvaluationRunRead.model_validate(run).model_dump(mode="json"))

    source_type_ids = {(kind, str(source_id)) for kind, source_id in source_ids}
    metrics = list(db.scalars(select(MetricRecord).where(
        MetricRecord.patient_profile_id == profile.id,
        MetricRecord.source_id.in_([UUID(value) for _, value in source_type_ids]),
    ).order_by(MetricRecord.measured_at.desc()))) if source_type_ids else []
    evidences = list(db.scalars(select(EvidenceRecord).where(
        EvidenceRecord.patient_profile_id == profile.id,
        EvidenceRecord.source_id.in_([UUID(value) for _, value in source_type_ids]),
    ).order_by(EvidenceRecord.measured_at.desc()))) if source_type_ids else []
    revision_history = []
    for run in runs:
        for revision in run.get("review_revisions", []):
            revision_history.append({
                "id": str(revision.get("id")),
                "run_id": run["id"],
                "action": revision.get("review_action"),
                "reason": revision.get("reason"),
                "created_at": revision.get("created_at"),
                "reviewer_user_id": str(revision.get("reviewer_user_id")) if revision.get("reviewer_user_id") else None,
                "automatic": revision.get("automatic_value_snapshot") or {},
                "revised": revision.get("revised_value_snapshot") or {},
                "recomputed_run_id": str(revision.get("recomputed_run_id")) if revision.get("recomputed_run_id") else None,
            })
    events = list(db.scalars(select(AttentionItemEvent).where(AttentionItemEvent.attention_item_id == item.id).order_by(AttentionItemEvent.created_at.asc())))
    active_plan = None
    if plan:
        active_plan = {
            "id": str(plan.id),
            "version_number": plan.version_number,
            "stage_focus": plan.stage_focus,
            "status": plan.status,
        }
    audio_available = any(attempt["audio"] for attempt in attempts) or any(turn["audio"] for dialogue in dialogues for turn in dialogue["turns"])
    return {
        "attention": _attention_payload(db, item),
        "patient": {"id": str(patient.id), "profile_id": str(profile.id), "name": patient.username},
        "goal": {"id": str(goal.id), "category": goal.category, "description": goal.description} if goal else None,
        "active_plan": active_plan,
        "source": {
            "tasks": [row["task"] for row in attempts + [{"task": dialogue["task"]} for dialogue in dialogues] if row.get("task")],
            "attempts": attempts,
            "dialogues": dialogues,
        },
        "audio_assets": [{"file_id": entry["audio"]["file_id"], "url": entry["audio"]["url"]} for entry in attempts if entry["audio"]] + [
            {"file_id": turn["audio"]["file_id"], "url": turn["audio"]["url"]}
            for dialogue in dialogues for turn in dialogue["turns"] if turn["audio"]
        ],
        "evaluation_runs": runs,
        "metrics": [{
            "id": str(row.id), "code": row.code, "value": row.value, "unit": row.unit, "status": row.status,
            "quality": row.quality or {}, "evidence_ids": row.evidence_ids or [], "measured_at": row.measured_at.isoformat(),
        } for row in metrics],
        "evidence": [{
            "id": str(row.id), "type": row.evidence_type, "source_type": row.source_type, "source_id": str(row.source_id),
            "quality_status": row.quality_status, "provider": row.provider, "provider_version": row.provider_version,
            "payload": row.payload or {}, "measured_at": row.measured_at.isoformat(),
        } for row in evidences],
        "review_history": sorted(revision_history, key=lambda row: row["created_at"] or ""),
        "events": [{
            "id": str(row.id), "event_type": row.event_type, "from_status": row.from_status,
            "to_status": row.to_status, "note": row.note, "related_refs": row.related_refs or {},
            "created_at": row.created_at.isoformat(),
        } for row in events],
        "quality": {
            "audio_available": audio_available,
            "audio_missing": not audio_available,
            "has_evaluation": bool(runs),
            "source_refs_resolved": bool(tasks),
        },
        "available_actions": ["confirm", "correct", "unjudgeable"] if runs else ["mark_waiting_information"],
    }
