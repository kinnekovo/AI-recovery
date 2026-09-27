"""Shadow canonical mapping for completed functional dialogue sessions.

This deliberately consumes persisted dialogue evidence only.  It neither calls nor
changes the legacy ScenarioDialogueEvaluation and it is not a profile/policy input.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.algorithm_config import config_entry, config_value
from app.modules.evaluation_runs.model import EvaluationReviewRevision, EvaluationRun
from app.modules.evaluation_runs.schema import (
    EvaluationDimensionResultCreate, EvaluationReviewRevisionCreate, EvaluationRunCreate,
    InputProvenanceSnapshot, QualityGateSnapshot,
)
from app.modules.evaluation_runs.service import adopt_candidate_run, create_candidate_run, get_run, get_run_for_professional, resolve_evaluation_write_failure
from app.modules.scenario_dialogues.model import DialogueSpeaker, DialogueStatus, ScenarioDialogueSession, ScenarioDialogueTurn
from app.modules.training.model import SessionTask
from app.modules.users.model import User

ALGORITHM_VERSION = "functional-communication-eval-v3.0"
DOMAIN = "functional_communication"
RESPONSE_ACTIONS = {"opening", "clarify", "clarify_current", "acknowledge_and_ask", "ask_optional", "repair", "confirm", "confirming"}


def _fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _turn_snapshot(turn: ScenarioDialogueTurn) -> dict:
    return {"id": str(turn.id), "index": turn.turn_index, "speaker": turn.speaker.value, "dialogue_act": turn.dialogue_act,
            "text": turn.text, "asr_provider": turn.asr_provider, "llm_provider": turn.llm_provider,
            "llm_model_version": turn.llm_model_version, "llm_prompt_version": turn.llm_prompt_version,
            "semantic_evidence": deepcopy(turn.semantic_evidence or {})}


def _is_formal_provider(value: str | None) -> bool:
    return value not in {"mock", "fallback", "unknown", ""}


def _build(dialogue: ScenarioDialogueSession, turns: list[ScenarioDialogueTurn], *, review_override: dict | None = None) -> EvaluationRunCreate:
    contract = deepcopy(dialogue.contract_snapshot or {})
    patient = [turn for turn in turns if turn.speaker == DialogueSpeaker.patient]
    required_units = [x for x in contract.get("required_information_units", []) if isinstance(x, dict) and x.get("id")]
    required_ids = {str(x["id"]) for x in required_units}
    limitations: list[str] = []
    gate_reasons: list[str] = []
    evidence: list[tuple[ScenarioDialogueTurn, dict]] = []
    for turn in patient:
        semantic = turn.semantic_evidence or {}
        if semantic.get("source") != "llm_structured":
            gate_reasons.append("semantic_provider_not_formal")
        if not _is_formal_provider(turn.asr_provider):
            gate_reasons.append("asr_provider_not_formal")
        for unit in semantic.get("information_units", []) if isinstance(semantic.get("information_units"), list) else []:
            if not isinstance(unit, dict) or not isinstance(unit.get("quote"), str) or not unit["quote"] or unit["quote"] not in turn.text:
                gate_reasons.append("semantic_citation_unlocatable")
                continue
            if not isinstance(unit.get("confidence"), (float, int)) or float(unit["confidence"]) < config_value("scenario_dialogue_evidence_confidence_min"):
                gate_reasons.append("semantic_measurement_quality_insufficient")
            evidence.append((turn, unit))
    if dialogue.status != DialogueStatus.completed:
        gate_reasons.append("dialogue_not_completed")
    if not patient:
        gate_reasons.append("no_patient_utterance")
    if not dialogue.contract_version:
        gate_reasons.append("contract_version_missing")
    collected = {str(unit.get("id")) for _, unit in evidence if unit.get("id")}
    information = round(100 * len(required_ids & collected) / len(required_ids), 1) if required_ids else 0.0
    goal_status = "achieved" if required_ids and required_ids <= collected else ("partly_achieved" if collected else "not_achieved")
    goal_value = float(config_value("scenario_dialogue_goal_scores")[goal_status])
    relevant = [t for t in patient if any(t.id == owner.id for owner, _ in evidence)]
    response_opportunities = [t for t in turns if t.speaker == DialogueSpeaker.agent and t.dialogue_act in RESPONSE_ACTIONS]
    response_count = sum(1 for i, t in enumerate(turns) if t.speaker == DialogueSpeaker.agent and t.dialogue_act in RESPONSE_ACTIONS and any(x.speaker == DialogueSpeaker.patient for x in turns[i + 1:]))
    response = round(100 * response_count / len(response_opportunities), 1) if response_opportunities else 0.0
    relevance = round(100 * len(relevant) / len(patient), 1) if patient else 0.0
    penalties = config_value("scenario_dialogue_independence_penalties")
    independence = max(0.0, 100 - dialogue.maximum_prompt_level * penalties["maximum_prompt_level"] - dialogue.prompt_count * penalties["prompt_count"])
    repairs = [i for i, t in enumerate(turns) if t.speaker == DialogueSpeaker.agent and t.dialogue_act == "repair"]
    repair_values = []
    for index in repairs:
        answer = next((x for x in turns[index + 1:] if x.speaker == DialogueSpeaker.patient), None)
        repair_values.append(100.0 if answer and any(owner.id == answer.id for owner, _ in evidence) else 0.0)
    quality_reasons = sorted(set(gate_reasons))
    formal = not quality_reasons
    profile_eligible = formal and dialogue.evaluation_role != "generalization_probe"
    ineligibility = ([] if profile_eligible else (["generalization_probe_excluded"] if dialogue.evaluation_role == "generalization_probe" else quality_reasons or ["shadow_not_profile_input"]))
    if dialogue.status != DialogueStatus.completed or not patient:
        result_status = "unscorable"
    elif formal:
        result_status = "formal"
    else:
        result_status = "review_required"
    measurement = {"semantic_provider": "llm_structured", "minimum_confidence": config_entry("scenario_dialogue_evidence_confidence_min"), "quality_reasons": quality_reasons}
    base_evidence = {"required_information_unit_ids": sorted(required_ids), "collected_information_unit_ids": sorted(collected), "citations": [{"turn_id": str(t.id), **u} for t, u in evidence]}
    dimensions = [
        EvaluationDimensionResultCreate(dimension_code="goal_achievement", value=goal_value, level=goal_status, unit="%", status="measured", measurement_quality=measurement, evidence_snapshot=base_evidence, limitations=quality_reasons),
        EvaluationDimensionResultCreate(dimension_code="information_sufficiency", value=information, unit="%", status="measured", measurement_quality=measurement, evidence_snapshot=base_evidence, limitations=quality_reasons),
        EvaluationDimensionResultCreate(dimension_code="response_ability", value=response, unit="%", status="measured", measurement_quality=measurement, evidence_snapshot={"opportunity_count": len(response_opportunities), "answered_count": response_count}, limitations=quality_reasons),
        EvaluationDimensionResultCreate(dimension_code="relevance_and_organization", value=relevance, unit="%", status="measured", measurement_quality=measurement, evidence_snapshot={"patient_turn_count": len(patient), "evidence_supported_turn_count": len(relevant)}, limitations=quality_reasons),
        EvaluationDimensionResultCreate(dimension_code="independence", value=independence, unit="engineering_score", status="measured", measurement_quality={"source": "persisted_prompt_events"}, evidence_snapshot={"prompt_count": dialogue.prompt_count, "maximum_prompt_level": dialogue.maximum_prompt_level, "penalties": config_entry("scenario_dialogue_independence_penalties")}, limitations=[]),
        EvaluationDimensionResultCreate(dimension_code="repair_ability", value=(round(sum(repair_values) / len(repair_values), 1) if repairs else None), unit="%", status=("measured" if repairs else "not_observed"), measurement_quality=measurement, evidence_snapshot={"repair_opportunity_count": len(repairs)}, limitations=(quality_reasons if repairs else ["no_repair_opportunity"])),
    ]
    if review_override:
        for dimension in dimensions:
            patch = review_override.get(dimension.dimension_code, review_override if len(dimensions) == 1 else {})
            if not isinstance(patch, dict):
                continue
            if patch.get("status") == "unjudgeable":
                dimension.status, dimension.value, dimension.level = "unavailable", None, "unjudgeable"
            else:
                for key in ("value", "level", "unit"):
                    if key in patch: setattr(dimension, key, patch[key])
                if "evidence_snapshot" in patch and isinstance(patch["evidence_snapshot"], dict): dimension.evidence_snapshot.update(patch["evidence_snapshot"])
        result_status, profile_eligible, ineligibility = "review_required", False, ["clinician_revision_requires_future_reassessment"]
    provenance = {"source_snapshot": {"dialogue_session_id": str(dialogue.id), "session_task_id": str(dialogue.session_task_id), "training_session_id": str(dialogue.training_session_id), "template_contract": contract, "evaluation_role": dialogue.evaluation_role, "dialogue_status": dialogue.status.value, "turns": [_turn_snapshot(t) for t in turns]}, "providers": {"semantic_schema": "scenario-semantic-evidence-v3", "authored_reply_fallback_used": any(t.speaker == DialogueSpeaker.agent and t.llm_provider is None for t in turns), "asr_providers": sorted({t.asr_provider or "not_recorded" for t in patient})}, "contract_version": dialogue.contract_version}
    fingerprint_source = {"algorithm_version": ALGORITHM_VERSION, "contract": contract, "contract_version": dialogue.contract_version, "turns": provenance["source_snapshot"]["turns"], "review_override": review_override or {}}
    return EvaluationRunCreate(patient_profile_id=_profile_id(dialogue), domain=DOMAIN, source_type="dialogue_session", source_id=dialogue.id, algorithm_version=ALGORITHM_VERSION, input_fingerprint=_fingerprint(fingerprint_source), config_snapshot={"functional_dimensions": ["goal_achievement", "information_sufficiency", "response_ability", "relevance_and_organization", "independence", "repair_ability"], "goal_scores": config_entry("scenario_dialogue_goal_scores"), "independence_penalties": config_entry("scenario_dialogue_independence_penalties"), "evidence_confidence_min": config_entry("scenario_dialogue_evidence_confidence_min")}, input_provenance=InputProvenanceSnapshot(**provenance), quality_gate=QualityGateSnapshot(eligible=formal, reasons=quality_reasons, algorithm_version=ALGORITHM_VERSION, measurement_quality="semantic_evidence"), result_status=result_status, profile_eligibility=profile_eligible, profile_ineligibility_reasons=ineligibility, limitations=quality_reasons, dimensions=dimensions)


def _profile_id(dialogue: ScenarioDialogueSession):
    # supplied by loader in write path, kept on transient object to avoid schema changes
    return dialogue._v3_patient_profile_id


def _load_dialogue(db: Session, dialogue_id: UUID) -> tuple[ScenarioDialogueSession, list[ScenarioDialogueTurn]]:
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue: raise HTTPException(status_code=404, detail="场景对话不存在")
    profile_id = db.scalar(select(SessionTask.training_session_id).where(SessionTask.id == dialogue.session_task_id))
    task = db.get(SessionTask, dialogue.session_task_id)
    dialogue._v3_patient_profile_id = task.session.patient_profile_id
    turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id).order_by(ScenarioDialogueTurn.turn_index)))
    return dialogue, turns


def write_functional_v3_run(db: Session, dialogue_id: UUID):
    dialogue, turns = _load_dialogue(db, dialogue_id)
    payload = _build(dialogue, turns)
    existing = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "dialogue_session", EvaluationRun.source_id == dialogue.id, EvaluationRun.domain == DOMAIN, EvaluationRun.algorithm_version == ALGORITHM_VERSION, EvaluationRun.input_fingerprint == payload.input_fingerprint))
    if existing:
        run = existing if existing.adoption_status == "adopted" else adopt_candidate_run(db, existing.id)
    else:
        candidate = create_candidate_run(db, payload)
        run = adopt_candidate_run(db, candidate.id)
    resolve_evaluation_write_failure(db, source_type="dialogue_session", source_id=dialogue.id, domain=DOMAIN,
        algorithm_version=ALGORITHM_VERSION, run=run)
    return run


def get_functional_run_for_professional(db: Session, user: User, dialogue_id: UUID):
    dialogue, _ = _load_dialogue(db, dialogue_id)
    run = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "dialogue_session", EvaluationRun.source_id == dialogue.id, EvaluationRun.domain == DOMAIN, EvaluationRun.adoption_status == "adopted"))
    if not run: raise HTTPException(status_code=404, detail="该场景尚无 V3 影子评估结果")
    return get_run_for_professional(db, user, run.id)


def review_or_recompute(db: Session, user: User, run_id: UUID, payload: EvaluationReviewRevisionCreate | None = None):
    current = get_run(db, run_id)
    if current.domain != DOMAIN: raise HTTPException(status_code=409, detail="该评估不是场景沟通 V3 结果")
    get_run_for_professional(db, user, run_id)
    request_key = _review_request_key(run_id, user.id, payload) if payload else None
    if request_key:
        existing_revision = db.scalar(select(EvaluationReviewRevision).where(EvaluationReviewRevision.evaluation_run_id == run_id, EvaluationReviewRevision.review_request_key == request_key))
        if existing_revision:
            return (get_run(db, existing_revision.recomputed_run_id) if existing_revision.recomputed_run_id else current), existing_revision
    if payload and payload.review_action == "confirmed":
        revision = EvaluationReviewRevision(evaluation_run_id=run_id, **payload.model_copy(update={"reviewer_user_id": user.id, "recomputed_run_id": None, "review_request_key": request_key}).model_dump())
        db.add(revision); db.commit(); return current, revision
    dialogue, turns = _load_dialogue(db, current.source_id)
    override = _review_override(current, payload)
    rebuilt = _build(dialogue, turns, review_override=override)
    same = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "dialogue_session", EvaluationRun.source_id == dialogue.id, EvaluationRun.domain == DOMAIN, EvaluationRun.input_fingerprint == rebuilt.input_fingerprint))
    if same: return same, None
    try:
        candidate = create_candidate_run(db, rebuilt, commit=False)
        revision = EvaluationReviewRevision(evaluation_run_id=run_id, **(payload or EvaluationReviewRevisionCreate(review_action="corrected")).model_copy(update={"reviewer_user_id": user.id, "recomputed_run_id": candidate.id, "review_request_key": request_key}).model_dump())
        db.add(revision); db.flush()
        adopted = adopt_candidate_run(db, candidate.id, commit=False)
        db.commit()
        return adopted, revision
    except Exception:
        db.rollback(); raise


def _review_request_key(run_id: UUID, user_id: UUID, payload: EvaluationReviewRevisionCreate | None) -> str:
    if not payload:
        return _fingerprint({"run_id": str(run_id), "kind": "recompute"})
    # Server-derived key prevents a client from accidentally producing duplicate
    # immutable revisions while retaining the option to supply an explicit key.
    return payload.review_request_key or _fingerprint({"run_id": str(run_id), "reviewer": str(user_id), "action": payload.review_action,
        "dimension_result_id": str(payload.dimension_result_id) if payload.dimension_result_id else None,
        "automatic": payload.automatic_value_snapshot, "revised": payload.revised_value_snapshot,
        "override": payload.evidence_override, "reason": payload.reason})


def _review_override(current: EvaluationRun, payload: EvaluationReviewRevisionCreate | None) -> dict:
    if not payload:
        return {}
    target = next((item for item in current.dimension_results if item.id == payload.dimension_result_id), None)
    if payload.dimension_result_id and not target:
        raise HTTPException(status_code=409, detail="复核维度不属于该评估运行")
    code = target.dimension_code if target else None
    patch = deepcopy(payload.revised_value_snapshot or {})
    if payload.review_action == "unjudgeable":
        patch["status"] = "unjudgeable"
    if payload.evidence_override:
        patch["evidence_snapshot"] = deepcopy(payload.evidence_override)
    return {code: patch} if code else patch
