from __future__ import annotations
import hashlib, json
from datetime import timedelta
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.database.base import utc_now
from app.modules.controlled_policy import adapter
from app.modules.controlled_policy.model import (ControlledActionApproval, ControlledActionAuditEvent,
    ControlledActionExecution, ControlledActionObservation, ControlledActionProposal, ControlledActionSafetyEvent)
from app.modules.controlled_policy.policy import (ALLOWED_ACTION_TYPES, APPROVAL_VALIDITY, ELIGIBLE_VALIDATION_STATUSES,
    POLICY, PROPOSAL_VALIDITY, VERSION)
from app.modules.policy_v2.model import PolicyDecision
from app.modules.policy_validation.model import PolicyValidationRegistry
from app.modules.profile_v2.model import PatientProfileSnapshot
from app.modules.training.model import SessionTask, TrainingSession

def _fail(code: str):
    raise ValueError(code)

def _session(db, session_id):
    return db.scalar(select(TrainingSession).where(TrainingSession.id == session_id).options(
        selectinload(TrainingSession.session_tasks).selectinload(SessionTask.task_template)))

def _fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def _event(db, proposal, event_type, actor=None, execution=None, payload=None):
    db.add(ControlledActionAuditEvent(proposal_id=proposal.id, execution_id=execution.id if execution else None,
        event_type=event_type, actor_user_id=getattr(actor, "id", None), payload=payload or {}))

def _safety(db, patient_profile_id, code, proposal=None, details=None):
    db.add(ControlledActionSafetyEvent(proposal_id=proposal.id if proposal else None, patient_profile_id=patient_profile_id,
        severity="blocked", code=code, details=details or {}))

def _registry(db, decision):
    return db.scalar(select(PolicyValidationRegistry).where(PolicyValidationRegistry.policy_version == decision.policy_version,
        PolicyValidationRegistry.rules_version == decision.rules_version))

def _eligibility(db, decision, session=None):
    if not decision: _fail("policy_decision_missing")
    if decision.mode != "shadow": _fail("decision_not_shadow")
    if decision.status in {"superseded", "invalidated"}: _fail("decision_invalidated")
    registry = _registry(db, decision)
    if not registry: _fail("activation_not_eligible")
    if registry.validation_status == "suspended": _fail("activation_suspended")
    if registry.validation_status not in ELIGIBLE_VALIDATION_STATUSES: _fail("activation_not_eligible")
    # Governance can only restrict V3.8; it can never grant runtime permission.
    if session:
        from app.modules.controlled_governance.model import ControlledActionGovernanceRegistry
        from app.modules.controlled_governance.model import ControlledActivationEvaluationRun
        from app.modules.controlled_policy.adapter import VERSION as adapter_version
        action_type = getattr(session, "_controlled_action_type", None)
        if action_type:
            governance = db.scalar(select(ControlledActionGovernanceRegistry).where(ControlledActionGovernanceRegistry.policy_version == decision.policy_version, ControlledActionGovernanceRegistry.rules_version == decision.rules_version, ControlledActionGovernanceRegistry.action_type == action_type))
            if governance and governance.governance_status == "suspended": _fail("governance_suspended")
            if governance and governance.latest_evaluation_run_id:
                run = db.get(ControlledActivationEvaluationRun, governance.latest_evaluation_run_id)
                if run and run.adapter_version != adapter_version: _fail("revalidation_required")
    latest = db.scalar(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == decision.patient_profile_id)
        .order_by(PatientProfileSnapshot.generated_at.desc()))
    if not decision.profile_snapshot_id or not latest or latest.id != decision.profile_snapshot_id or latest.status in {"failed", "insufficient"}:
        _fail("stale_profile")
    if session and (session.patient_profile_id != decision.patient_profile_id or session.status.value != "in_progress"):
        _fail("training_state_incompatible")
    return registry

def _action_from_decision(decision, action_type):
    if action_type not in ALLOWED_ACTION_TYPES: _fail("unsupported_action")
    payload = decision.decision_payload or {}
    if action_type == "training_focus_override":
        item = next((item for item in payload.get("training_focus", []) if item.get("priority") != "not_eligible"), None)
        if not item or not item.get("dimension_code"): _fail("no_supported_training_target")
        return item["dimension_code"], list(item.get("reason_codes", []))
    action = (payload.get("difficulty") or {}).get("recommended_difficulty_action")
    if action == "increase": return 1, ["POLICY_DIFFICULTY_INCREASE"]
    if action == "decrease": return -1, ["POLICY_DIFFICULTY_DECREASE"]
    _fail("unsupported_action")

def create_proposal(db: Session, decision_id: UUID, action_type: str, target_session_id: UUID, actor=None):
    decision = db.get(PolicyDecision, decision_id); session = _session(db, target_session_id)
    try:
        if session: session._controlled_action_type = action_type
        registry = _eligibility(db, decision, session)
        if not session: _fail("training_session_missing")
        value, reasons = _action_from_decision(decision, action_type)
        proposed, current, scope = adapter.proposal_preview(session, action_type, value)
    except ValueError as exc:
        if decision: _safety(db, decision.patient_profile_id, str(exc), details={"decision_id": str(decision_id)}) ; db.commit()
        raise
    fingerprint = _fingerprint({"decision": str(decision.id), "action": action_type, "session": str(session.id),
        "proposed": proposed, "current": current, "policy": VERSION})
    existing = db.scalar(select(ControlledActionProposal).where(ControlledActionProposal.proposal_fingerprint == fingerprint))
    if existing: return existing
    conflicting = db.scalar(select(ControlledActionProposal).where(ControlledActionProposal.patient_profile_id == decision.patient_profile_id,
        ControlledActionProposal.target_training_session_id == session.id, ControlledActionProposal.action_type == action_type,
        ControlledActionProposal.status.in_(["pending_review", "approved"])))
    if conflicting: _fail("concurrent_action_conflict")
    proposal = ControlledActionProposal(policy_decision_id=decision.id, patient_profile_id=decision.patient_profile_id,
        target_training_session_id=session.id, action_type=action_type, proposed_value=proposed, current_value=current,
        expected_scope=scope, reason_codes=reasons, policy_version=decision.policy_version, rules_version=decision.rules_version,
        validation_run_id=registry.latest_validation_run_id, profile_snapshot_id=decision.profile_snapshot_id,
        activation_policy_version=VERSION, proposal_fingerprint=fingerprint, expires_at=utc_now() + PROPOSAL_VALIDITY)
    try:
        db.add(proposal); db.flush(); _event(db, proposal, "created", actor, payload={"policy": POLICY}); db.commit(); db.refresh(proposal); return proposal
    except IntegrityError:
        db.rollback(); return db.scalar(select(ControlledActionProposal).where(ControlledActionProposal.proposal_fingerprint == fingerprint))

def _owned(db, proposal_id, patient_profile_id):
    proposal = db.get(ControlledActionProposal, proposal_id)
    if not proposal or proposal.patient_profile_id != patient_profile_id: _fail("proposal_missing")
    return proposal

def _expire_if_needed(db, proposal):
    now = utc_now()
    deadline = proposal.expires_at
    if getattr(deadline, "tzinfo", None) is None:
        now = now.replace(tzinfo=None)
    if proposal.status in {"pending_review", "approved"} and deadline <= now:
        proposal.status = "expired"; _event(db, proposal, "expired"); db.commit()
    return proposal.status == "expired"

def approve(db, proposal_id, patient_profile_id, therapist, comment=None):
    proposal = _owned(db, proposal_id, patient_profile_id)
    if _expire_if_needed(db, proposal): _fail("proposal_expired")
    if proposal.status != "pending_review": _fail("invalid_status_transition")
    decision = db.get(PolicyDecision, proposal.policy_decision_id)
    try:
        session = _session(db, proposal.target_training_session_id); session._controlled_action_type = proposal.action_type
        _eligibility(db, decision, session)
    except ValueError as exc: _safety(db, proposal.patient_profile_id, str(exc), proposal); db.commit(); raise
    approval_until = utc_now() + APPROVAL_VALIDITY
    if getattr(proposal.expires_at, "tzinfo", None) is None: approval_until = approval_until.replace(tzinfo=None)
    approval = ControlledActionApproval(proposal_id=proposal.id, therapist_user_id=therapist.id, approved_action=proposal.proposed_value,
        approval_comment=comment, approval_valid_until=min(proposal.expires_at, approval_until))
    proposal.status = "approved"; db.add(approval); _event(db, proposal, "approved", therapist); db.commit(); db.refresh(proposal); return proposal

def reject(db, proposal_id, patient_profile_id, therapist, reason_code, comment=None):
    proposal = _owned(db, proposal_id, patient_profile_id)
    if _expire_if_needed(db, proposal): _fail("proposal_expired")
    if proposal.status != "pending_review": _fail("invalid_status_transition")
    proposal.status = "rejected"; _event(db, proposal, "rejected", therapist, payload={"reason_code": reason_code, "comment": comment}); db.commit(); return proposal

def _same_state(proposal, session):
    if proposal.action_type == "training_focus_override":
        return proposal.current_value.get("order_indexes") == {str(t.id): t.order_index for t in session.session_tasks}
    task = next((t for t in session.session_tasks if str(t.id) == proposal.proposed_value.get("task_id")), None)
    return bool(task) and task.prompt_level == proposal.current_value.get("prompt_level")

def apply(db, proposal_id, patient_profile_id, therapist, target_session_id=None):
    proposal = _owned(db, proposal_id, patient_profile_id)
    if target_session_id and target_session_id != proposal.target_training_session_id: _fail("scope_mismatch")
    existing = db.scalar(select(ControlledActionExecution).where(ControlledActionExecution.proposal_id == proposal.id))
    if existing: _fail("duplicate_apply")
    if _expire_if_needed(db, proposal): _fail("proposal_expired")
    if proposal.status != "approved": _fail("approval_required")
    approval = db.scalar(select(ControlledActionApproval).where(ControlledActionApproval.proposal_id == proposal.id))
    approval_now = utc_now()
    if approval and getattr(approval.approval_valid_until, "tzinfo", None) is None: approval_now = approval_now.replace(tzinfo=None)
    if not approval or approval.approval_valid_until <= approval_now: _fail("approval_required")
    decision = db.get(PolicyDecision, proposal.policy_decision_id); session = _session(db, proposal.target_training_session_id)
    try:
        session._controlled_action_type = proposal.action_type
        _eligibility(db, decision, session)
        if not _same_state(proposal, session): _fail("state_conflict")
        before, after, changed = adapter.apply_to_session(session, proposal.action_type, proposal.proposed_value)
        execution = ControlledActionExecution(proposal_id=proposal.id, patient_profile_id=proposal.patient_profile_id,
            training_session_id=session.id, before_state=before, after_state=after, applied_by_user_id=therapist.id,
            status="no_op" if not changed else "applied")
        proposal.status = "applied"; db.add(execution); db.flush(); _event(db, proposal, "no_op" if not changed else "applied", therapist, execution)
        db.commit(); db.refresh(execution); return execution
    except ValueError as exc:
        db.rollback(); _safety(db, proposal.patient_profile_id, str(exc), proposal); _event(db, proposal, "apply_blocked", therapist, payload={"code": str(exc)}); db.commit(); raise

def rollback(db, execution_id, patient_profile_id, therapist, reason_code, comment=None):
    execution = db.get(ControlledActionExecution, execution_id)
    if not execution or execution.patient_profile_id != patient_profile_id: _fail("execution_missing")
    if execution.status not in {"applied", "no_op"} or execution.rolled_back_at: _fail("invalid_status_transition")
    proposal = db.get(ControlledActionProposal, execution.proposal_id); session = _session(db, execution.training_session_id)
    if proposal.action_type == "training_focus_override":
        before = execution.before_state["order_indexes"]
        for task in session.session_tasks: task.order_index = int(before[str(task.id)])
    else:
        task = next((t for t in session.session_tasks if str(t.id) == proposal.proposed_value["task_id"]), None)
        if not task: _fail("state_conflict")
        task.prompt_level = int(execution.before_state["prompt_level"])
    # Keep the execution's applied/no-op record immutable; rollback is an appended audit state.
    execution.rolled_back_at = utc_now(); execution.rolled_back_by_user_id = therapist.id
    execution.rollback_reason_code = reason_code; execution.rollback_comment = comment; proposal.status = "rolled_back"
    _event(db, proposal, "rolled_back", therapist, execution, {"reason_code": reason_code, "comment": comment}); db.commit(); return execution

def observe(db, execution_id, patient_profile_id, therapist, outcome, feedback=None):
    execution = db.get(ControlledActionExecution, execution_id)
    if not execution or execution.patient_profile_id != patient_profile_id: _fail("execution_missing")
    existing = db.scalar(select(ControlledActionObservation).where(ControlledActionObservation.execution_id == execution.id))
    if existing: return existing
    row = ControlledActionObservation(execution_id=execution.id, outcome=outcome, therapist_feedback=feedback); db.add(row)
    _event(db, db.get(ControlledActionProposal, execution.proposal_id), "observed", therapist, execution, {"outcome": outcome}); db.commit(); db.refresh(row); return row

def list_history(db, patient_profile_id):
    return list(db.scalars(select(ControlledActionProposal).where(ControlledActionProposal.patient_profile_id == patient_profile_id)
        .order_by(ControlledActionProposal.created_at.desc())))

def analytics(db, patient_profile_id):
    rows = list_history(db, patient_profile_id); executions = list(db.scalars(select(ControlledActionExecution).where(ControlledActionExecution.patient_profile_id == patient_profile_id)))
    def count(items):
        result = {}
        for item in items: result[item] = result.get(item, 0) + 1
        return result
    return {"proposal_count": len(rows), "proposal_status_distribution": count(row.status for row in rows),
        "action_type_distribution": count(row.action_type for row in rows), "execution_distribution": count(row.status for row in executions),
        "approval_rate": sum(row.status in {"approved", "applied", "rolled_back"} for row in rows) / len(rows) if rows else None,
        "note": "工程行为指标，不表示临床有效性或安全性。"}
