from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.algorithm_config import config_value
from app.modules.scenario_dialogues.model import DialogueSpeaker, DialogueState, DialogueStatus, ScenarioDialogueEvaluation, ScenarioDialogueSession, ScenarioDialogueTurn
from app.modules.scenario_dialogues.schema import ScenarioDialogueEvaluationRead, ScenarioDialogueRead, ScenarioDialogueReviewUpdate, TherapistScenarioDialogueListItem
from app.database.base import utc_now
from app.modules.training.model import SessionTask, TrainingType
from app.modules.users.model import PatientProfile, User
from app.modules.users.service import get_patient_profile
from app.integrations.llm.scenario_semantics import (
    ROLE_REPLY_PROMPT_VERSION,
    extract_evidence_with_status,
    generate_role_reply_with_status,
)
from app.modules.scenario_dialogues.policy import choose_dialogue_action, unit_by_id


def _owned_task(db: Session, user: User, task_id):
    task = db.get(SessionTask, task_id)
    profile = get_patient_profile(db, user)
    if not task or task.session.patient_profile_id != profile.id or task.task_template.task_type != TrainingType.scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景对话任务不存在")
    return task


def create_dialogue(db: Session, user: User, task_id):
    task = _owned_task(db, user, task_id)
    existing = db.scalar(select(ScenarioDialogueSession).where(ScenarioDialogueSession.session_task_id == task.id))
    if existing:
        return to_read(db, existing)
    # A session task owns the immutable contract snapshot used by the plan.  The
    # live template is only a compatibility fallback for legacy tasks created
    # before Product v2 began snapshotting task content.
    contract = (task.content_snapshot or {}).get("scoring_config") or task.task_template.scoring_config or {}
    if contract.get("mode") != "functional_scenario":
        raise HTTPException(status_code=400, detail="该场景尚未配置多轮沟通契约")
    session = ScenarioDialogueSession(
        training_session_id=task.training_session_id,
        session_task_id=task.id,
        contract_snapshot=contract,
        contract_version=str(contract.get("version", "scenario-dialogue-v1")),
        evaluation_role=str(contract.get("evaluation_role", "training")),
        current_state=DialogueState.collecting,
    )
    opening = str(contract.get("opening_line") or contract.get("display_prompt") or "您好，请问有什么需要帮助的吗？")
    db.add(session)
    db.flush()
    db.add(ScenarioDialogueTurn(dialogue_session_id=session.id, turn_index=1, speaker=DialogueSpeaker.agent, dialogue_act="opening", text=opening))
    db.commit()
    return to_read(db, session)


def get_dialogue(db: Session, user: User, dialogue_id):
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    _owned_task(db, user, dialogue.session_task_id)
    return to_read(db, dialogue)


def patient_trends(db: Session, user: User) -> dict:
    profile = get_patient_profile(db, user)
    rows = db.execute(
        select(ScenarioDialogueSession, ScenarioDialogueEvaluation)
        .join(SessionTask, SessionTask.id == ScenarioDialogueSession.session_task_id)
        .join(SessionTask.session)
        .outerjoin(ScenarioDialogueEvaluation, ScenarioDialogueEvaluation.dialogue_session_id == ScenarioDialogueSession.id)
        .where(SessionTask.session.has(patient_profile_id=profile.id), ScenarioDialogueSession.status == DialogueStatus.completed)
        .order_by(ScenarioDialogueSession.created_at.asc())
    ).all()
    buckets = {"training": [], "generalization_probe": []}
    for dialogue, evaluation in rows:
        buckets["generalization_probe" if dialogue.evaluation_role == "generalization_probe" else "training"].append((dialogue, evaluation))
    return {"training": _trend_summary(buckets["training"]), "generalization_probe": _trend_summary(buckets["generalization_probe"])}


def _trend_summary(rows: list[tuple[ScenarioDialogueSession, ScenarioDialogueEvaluation | None]]) -> dict:
    evaluated = [evaluation for _, evaluation in rows if evaluation]
    if not evaluated:
        return {"dialogue_count": len(rows), "independent_goal_achievement_rate": None, "median_information_score": None, "effective_response_rate": None, "average_prompt_level": None, "observed_repair_success_rate": None}
    values = sorted(item.information_score for item in evaluated)
    midpoint = len(values) // 2
    median = values[midpoint] if len(values) % 2 else round((values[midpoint - 1] + values[midpoint]) / 2, 1)
    repair = [item.repair_score for item in evaluated if item.repair_score is not None]
    independent_goals = [item for dialogue, item in rows if item and item.goal_status == "achieved" and dialogue.prompt_count == 0]
    return {
        "dialogue_count": len(rows),
        "independent_goal_achievement_rate": round(len(independent_goals) / len(evaluated), 3),
        "median_information_score": median,
        "effective_response_rate": round(sum(item.response_score for item in evaluated) / len(evaluated), 1),
        "average_prompt_level": round(sum(dialogue.maximum_prompt_level for dialogue, _ in rows) / len(rows), 2),
        "observed_repair_success_rate": round(sum(repair) / len(repair), 1) if repair else None,
    }


def get_evaluation(db: Session, user: User, dialogue_id) -> ScenarioDialogueEvaluationRead:
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    _owned_task(db, user, dialogue.session_task_id)
    if dialogue.status == DialogueStatus.active:
        raise HTTPException(status_code=409, detail="请在对话结束后查看整段评价")
    entity = ensure_evaluation(db, dialogue.id)
    db.commit()
    # Canonical V3.2 is shadow-only: legacy response is already durable and a
    # storage failure cannot alter its score, trends, or training flow.
    try:
        from app.modules.evaluation_runs.functional_communication_v3 import write_functional_v3_run
        write_functional_v3_run(db, dialogue.id)
    except Exception:
        db.rollback()
        from app.modules.evaluation_runs.functional_communication_v3 import ALGORITHM_VERSION, DOMAIN
        from app.modules.evaluation_runs.service import record_evaluation_write_failure
        record_evaluation_write_failure(db, source_type="dialogue_session", source_id=dialogue.id, domain=DOMAIN,
            algorithm_version=ALGORITHM_VERSION, failure_stage="shadow_write")
    return ScenarioDialogueEvaluationRead.model_validate(entity, from_attributes=True)


def ensure_evaluation(db: Session, dialogue_id) -> ScenarioDialogueEvaluation:
    """Materialize the legacy scenario evaluation for downstream projections.

    Product v2 completes a scenario from the dialogue lifecycle itself, so it
    cannot rely on a later read of the legacy evaluation endpoint to create the
    durable evaluation row.  This helper is intentionally idempotent and leaves
    transaction ownership to its caller.
    """
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    if dialogue.status == DialogueStatus.active:
        raise HTTPException(status_code=409, detail="场景对话尚未结束")
    entity = db.scalar(
        select(ScenarioDialogueEvaluation).where(
            ScenarioDialogueEvaluation.dialogue_session_id == dialogue.id
        )
    )
    if entity:
        return entity
    entity = _evaluate_dialogue(db, dialogue)
    db.add(entity)
    db.flush()
    return entity


def review_evaluation(db: Session, therapist: User, dialogue_id, payload: ScenarioDialogueReviewUpdate) -> ScenarioDialogueEvaluationRead:
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    task = db.get(SessionTask, dialogue.session_task_id)
    profile = db.get(PatientProfile, task.session.patient_profile_id) if task else None
    if not profile:
        raise HTTPException(status_code=404, detail="场景对话患者不存在")
    from app.modules.therapist.service import require_therapist_patient_access
    require_therapist_patient_access(db, therapist, profile.user_id)
    entity = db.scalar(select(ScenarioDialogueEvaluation).where(ScenarioDialogueEvaluation.dialogue_session_id == dialogue.id))
    if not entity:
        entity = _evaluate_dialogue(db, dialogue)
        db.add(entity)
        db.flush()
    entity.evidence_overrides = payload.evidence_overrides
    entity.review_notes = payload.review_notes
    entity.review_status = payload.review_status
    entity.reviewed_by_user_id = therapist.id
    entity.reviewed_at = utc_now()
    db.commit()
    return ScenarioDialogueEvaluationRead.model_validate(entity, from_attributes=True)


def get_dialogue_for_therapist(db: Session, therapist: User, dialogue_id) -> ScenarioDialogueRead:
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    _require_therapist_access(db, therapist, dialogue)
    return to_read(db, dialogue)


def list_dialogues_for_therapist(db: Session, therapist: User, patient_user_id) -> list[TherapistScenarioDialogueListItem]:
    from app.modules.therapist.service import require_therapist_patient_access
    profile = require_therapist_patient_access(db, therapist, patient_user_id)
    rows = db.execute(
        select(ScenarioDialogueSession, ScenarioDialogueEvaluation.review_status)
        .join(SessionTask, SessionTask.id == ScenarioDialogueSession.session_task_id)
        .join(SessionTask.session)
        .outerjoin(ScenarioDialogueEvaluation, ScenarioDialogueEvaluation.dialogue_session_id == ScenarioDialogueSession.id)
        .where(SessionTask.session.has(patient_profile_id=profile.id))
        .order_by(ScenarioDialogueSession.created_at.desc())
    ).all()
    return [TherapistScenarioDialogueListItem(id=item.id, created_at=item.created_at, status=item.status.value, current_state=item.current_state.value, communication_goal=str(item.contract_snapshot.get("communication_goal", "")), patient_turn_count=item.patient_turn_count, review_status=review_status) for item, review_status in rows]


def _require_therapist_access(db: Session, therapist: User, dialogue: ScenarioDialogueSession) -> None:
    task = db.get(SessionTask, dialogue.session_task_id)
    profile = db.get(PatientProfile, task.session.patient_profile_id) if task else None
    if not profile:
        raise HTTPException(status_code=404, detail="场景对话患者不存在")
    from app.modules.therapist.service import require_therapist_patient_access
    require_therapist_patient_access(db, therapist, profile.user_id)


def next_hint(db: Session, user: User, dialogue_id):
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue or dialogue.status != DialogueStatus.active:
        raise HTTPException(status_code=409, detail="当前对话不能请求提示")
    _owned_task(db, user, dialogue.session_task_id)
    hints = dialogue.contract_snapshot.get("prompt_hints") or dialogue.contract_snapshot.get("prompt_ladder") or []
    level = min(dialogue.maximum_prompt_level + 1, len(hints))
    if not level:
        raise HTTPException(status_code=404, detail="当前场景没有更多提示")
    dialogue.maximum_prompt_level = level
    dialogue.prompt_count += 1
    db.commit()
    return {"level": level, "text": str(hints[level - 1])}


def finish_dialogue(db: Session, user: User, dialogue_id) -> ScenarioDialogueRead:
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue:
        raise HTTPException(status_code=404, detail="场景对话不存在")
    _owned_task(db, user, dialogue.session_task_id)
    if dialogue.status != DialogueStatus.active:
        return to_read(db, dialogue)
    turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id).order_by(ScenarioDialogueTurn.turn_index)))
    dialogue.status = DialogueStatus.completed
    dialogue.current_state = DialogueState.completed
    db.add(ScenarioDialogueTurn(
        dialogue_session_id=dialogue.id,
        turn_index=(turns[-1].turn_index if turns else 0) + 1,
        speaker=DialogueSpeaker.agent,
        dialogue_act="patient_finish",
        text="好的，这一段练习先到这里。谢谢你的表达。",
    ))
    db.commit()
    return to_read(db, dialogue)


def add_patient_turn(
    db: Session,
    user: User,
    dialogue_id,
    transcript: str,
    *,
    audio_file_id=None,
    asr_provider: str | None = None,
    client_turn_id: str | None = None,
):
    dialogue = db.get(ScenarioDialogueSession, dialogue_id)
    if not dialogue or dialogue.status != DialogueStatus.active:
        raise HTTPException(status_code=409, detail="当前对话已经结束")
    _owned_task(db, user, dialogue.session_task_id)
    if client_turn_id:
        existing = db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id, ScenarioDialogueTurn.speaker == DialogueSpeaker.patient)).all()
        if any((turn.semantic_evidence or {}).get("client_turn_id") == client_turn_id for turn in existing):
            return to_read(db, dialogue)
    text = transcript.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请先完成本轮表达")
    safety_reply = _safety_escalation_reply(text)
    contract = dialogue.contract_snapshot
    # Two turns are enough for many real exchanges (problem → concrete request).
    # Never keep a patient talking just to satisfy an arbitrary turn count.
    minimum_turns = max(1, int(contract.get("minimum_patient_turns", 2)))
    max_turns = max(minimum_turns, int(contract.get("maximum_patient_turns", 5)))
    if dialogue.patient_turn_count >= max_turns:
        raise HTTPException(status_code=409, detail="本场对话已达到最大回合数")
    turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id).order_by(ScenarioDialogueTurn.turn_index)))
    previous_agent = next((turn for turn in reversed(turns) if turn.speaker == DialogueSpeaker.agent), None)
    previous_agent_metadata = (previous_agent.semantic_evidence or {}) if previous_agent else {}
    current_target_id = str(previous_agent_metadata.get("target_information_unit_id") or "") or None
    current_target = unit_by_id(contract, current_target_id)
    conversation_history = [
        {
            "speaker": "patient" if turn.speaker == DialogueSpeaker.patient else "agent",
            "dialogue_act": turn.dialogue_act,
            "text": turn.text,
        }
        for turn in turns
    ]
    previous_collected = _collected_unit_ids(db, dialogue.id, [])
    semantic_result = extract_evidence_with_status(
        contract,
        text,
        last_agent_question=previous_agent.text if previous_agent else None,
        current_target_information_unit=current_target,
        conversation_history=conversation_history,
        collected_information_unit_ids=sorted(previous_collected),
    )
    semantic = semantic_result.value if isinstance(semantic_result.value, dict) else None
    semantic_from_llm = semantic_result.status == "success" and semantic is not None and semantic.get("source") == "llm_structured"
    matched = semantic["information_units"] if semantic else _match_units(contract, text)
    if semantic is None:
        target_supported = bool(current_target_id and any(item.get("id") == current_target_id for item in matched))
        semantic = {
            "source": "contract_fallback",
            "information_units": matched,
            "answered_current_question": target_supported,
            "answered_target_id": current_target_id,
            "answer_status": "supported" if target_supported else "uncertain",
            "dialogue_act": "answer",
            "relevance": "relevant" if matched else "uncertain",
            "contradictions": [],
        }
    semantic.update({
        "llm_status": semantic_result.status,
        "llm_error_code": semantic_result.error_code,
        "llm_latency_ms": semantic_result.latency_ms,
        "fallback_used": not semantic_from_llm,
    })
    next_index = (turns[-1].turn_index if turns else 0) + 1
    db.add(ScenarioDialogueTurn(
        dialogue_session_id=dialogue.id, turn_index=next_index, speaker=DialogueSpeaker.patient,
        dialogue_act="response", text=text,
        audio_file_id=audio_file_id,
        asr_provider=asr_provider,
        llm_provider=semantic_result.provider if semantic_from_llm else None,
        llm_model_version=semantic_result.model if semantic_from_llm else None,
        llm_prompt_version=semantic.get("prompt_version") if semantic_from_llm else None,
        semantic_evidence={**semantic, "quote": text, "asr_provider": asr_provider, "client_turn_id": client_turn_id},
    ))
    dialogue.patient_turn_count += 1
    if safety_reply:
        dialogue.current_state = DialogueState.completed
        dialogue.status = DialogueStatus.aborted
        db.flush()
        db.add(ScenarioDialogueTurn(
            dialogue_session_id=dialogue.id, turn_index=next_index + 1, speaker=DialogueSpeaker.agent,
            dialogue_act="safety_escalation", text=safety_reply,
        ))
        db.commit()
        return to_read(db, dialogue)
    collected = _collected_unit_ids(db, dialogue.id, matched)
    decision = choose_dialogue_action(
        contract,
        collected=collected,
        patient_turn_count=dialogue.patient_turn_count,
        minimum_patient_turns=minimum_turns,
        maximum_patient_turns=max_turns,
        current_target_id=current_target_id,
        answered_current_question=semantic.get("answered_current_question"),
        answer_status=semantic.get("answer_status"),
        repair_already_offered=any(turn.dialogue_act == "repair" for turn in turns),
    )
    reply_target = decision.target
    dialogue.current_state = DialogueState(decision.state)
    if decision.action == "repair":
        repair = (contract.get("repair_opportunities") or [])[0]
        reply = str(repair.get("question") or repair.get("text") or "我想确认一下，你能换一种说法再告诉我吗？") if isinstance(repair, dict) else "我想确认一下，你能换一种说法再告诉我吗？"
        act = "repair"
    elif decision.action == "complete":
        dialogue.status = DialogueStatus.completed
        reply, act = _completion_reply(contract, text), "complete"
    elif decision.action == "confirm":
        reply, act = _confirmation_reply(contract), "confirm"
    elif decision.action == "close":
        dialogue.status = DialogueStatus.completed
        reply, act = "谢谢你的表达。这一轮先到这里，我们下次继续练习。", "close"
    else:
        target_id = str((reply_target or {}).get("id", ""))
        reply = _follow_up_question(contract, target_id, reply_target)
        act = decision.action if decision.action in {"acknowledge_and_ask", "clarify_current", "ask_optional"} else "clarify"
    # A closing instruction remains rule-owned, but active replies may be
    # contextualized as long as the model echoes the locked action and target.
    conversation_history = conversation_history + [{"speaker": "patient", "dialogue_act": "response", "text": text}]
    reply_result = generate_role_reply_with_status(
        contract,
        act,
        reply,
        conversation_history=conversation_history,
        current_patient_utterance=text,
        target_information_unit=reply_target,
        collected_information_unit_ids=sorted(collected),
        acknowledge_evidence=semantic.get("information_units", []),
    ) if act in {"clarify", "clarify_current", "acknowledge_and_ask", "ask_optional", "repair", "confirm", "complete"} else None
    generated_reply = reply_result.value if reply_result and isinstance(reply_result.value, str) else None
    if not generated_reply and act in {"acknowledge_and_ask", "clarify_current", "ask_optional", "confirm", "complete"}:
        reply = _acknowledging_fallback(text, reply, semantic.get("information_units", []))
    else:
        reply = generated_reply or reply
    db.flush()
    db.add(ScenarioDialogueTurn(
        dialogue_session_id=dialogue.id, turn_index=next_index + 1, speaker=DialogueSpeaker.agent,
        dialogue_act=act, text=reply,
        llm_provider=reply_result.provider if reply_result and reply_result.status == "success" else None,
        llm_model_version=reply_result.model if reply_result and reply_result.status == "success" else None,
        llm_prompt_version=ROLE_REPLY_PROMPT_VERSION if generated_reply else None,
        semantic_evidence={
            "source": "dialogue_policy_v1",
            "policy_action": decision.action,
            "policy_reason": decision.reason,
            "target_information_unit_id": str((reply_target or {}).get("id")) if reply_target else None,
            "llm_status": reply_result.status if reply_result else "not_requested",
            "llm_error_code": reply_result.error_code if reply_result else None,
            "llm_latency_ms": reply_result.latency_ms if reply_result else None,
            "fallback_used": not bool(generated_reply),
            "acknowledged_information_unit_ids": [str(item.get("id")) for item in semantic.get("information_units", []) if item.get("id")],
        },
    ))
    db.commit()
    return to_read(db, dialogue)


def _acknowledging_fallback(transcript: str, reply: str, information_units: list[dict]) -> str:
    """Keep the fallback grounded in the patient's words when LLM wording fails."""
    if not information_units:
        return reply
    quote = next((item.get("quote") for item in information_units if isinstance(item, dict) and item.get("quote")), transcript)
    quote = " ".join(str(quote).split()).strip().rstrip("。！？?!")
    if not quote:
        return reply
    if len(quote) > 20:
        quote = quote[:20] + "…"
    normalized_reply = reply.strip()
    if normalized_reply.startswith("好的，"):
        normalized_reply = normalized_reply[3:]
    return f"好的，我听到您说“{quote}”了。{normalized_reply}"


def _match_units(contract: dict, transcript: str) -> list[dict]:
    evidence = []
    for unit in contract.get("required_information_units", []) + contract.get("optional_information_units", []):
        if not isinstance(unit, dict):
            continue
        keywords = [item for item in unit.get("keywords", []) if isinstance(item, str)]
        hits = [item for item in keywords if item in transcript]
        if hits:
            evidence.append({"id": unit.get("id"), "label": unit.get("label"), "quote": transcript, "matched_terms": hits})
    return evidence


def _safety_escalation_reply(transcript: str) -> str | None:
    """Keep role-play out of urgent medical and self-harm situations.

    This is intentionally a conservative stop signal, not a diagnosis classifier.
    """
    urgent_terms = ("胸痛", "呼吸困难", "喘不过气", "昏倒", "意识不清", "自杀", "不想活", "伤害自己")
    if any(term in transcript for term in urgent_terms):
        return "这可能需要立即获得现实中的帮助。请马上联系身边可信任的人、当地急救服务或就近医疗机构；本次练习先暂停。"
    return None


def _follow_up_question(contract: dict, target_id: str, missing_unit: dict | None) -> str:
    """Choose a contract-authored follow-up, never a fixed carousel question.

    The contract may carry a list of objects or a mapping so authored scenarios can
    retain their own conversational wording.  The final fallback only names the
    currently missing semantic unit; it never reveals a model answer.
    """
    follow_ups = contract.get("follow_up_questions") or []
    if isinstance(follow_ups, dict):
        question = follow_ups.get(target_id)
        if isinstance(question, str) and question.strip():
            return question.strip()
    if isinstance(follow_ups, list):
        for item in follow_ups:
            if isinstance(item, dict) and item.get("target_information_unit") == target_id:
                question = item.get("question") or item.get("text")
                if isinstance(question, str) and question.strip():
                    return question.strip()
    label = str((missing_unit or {}).get("label") or "这方面的信息")
    return f"为了更好地帮助你，能再说说{label}吗？"


def _confirmation_reply(contract: dict) -> str:
    response = contract.get("confirmation_response")
    if isinstance(response, str) and response.strip():
        return response.strip()
    return "好的，我记下了。还有其他需要说明的吗？"


def _completion_reply(contract: dict, transcript: str) -> str:
    """End with the next conversational action, never a hollow acknowledgement."""
    response = contract.get("completion_response")
    if isinstance(response, str) and response.strip():
        return response.strip()
    if any(token in transcript for token in ("哪里", "怎么走", "在哪", "方向")):
        return "请向现场工作人员确认具体位置；他们会继续帮你安排下一步。"
    return "我明白你的需要了。接下来请按现场工作人员的指引办理。"


def _collected_unit_ids(db: Session, dialogue_id, latest: list[dict]) -> set[str]:
    turns = db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue_id, ScenarioDialogueTurn.speaker == DialogueSpeaker.patient)).all()
    evidence = latest + [unit for turn in turns for unit in (turn.semantic_evidence or {}).get("information_units", [])]
    return {str(unit.get("id")) for unit in evidence if unit.get("id")}


def to_read(db: Session, dialogue: ScenarioDialogueSession) -> ScenarioDialogueRead:
    turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id).order_by(ScenarioDialogueTurn.turn_index)))
    return ScenarioDialogueRead(
        id=dialogue.id, status=dialogue.status.value, current_state=dialogue.current_state.value,
        patient_turn_count=dialogue.patient_turn_count, prompt_count=dialogue.prompt_count,
        maximum_prompt_level=dialogue.maximum_prompt_level,
        communication_goal=str(dialogue.contract_snapshot.get("communication_goal", "")), turns=turns,
    )


def _evaluate_dialogue(db: Session, dialogue: ScenarioDialogueSession) -> ScenarioDialogueEvaluation:
    """Calculate the documented six dimensions from persisted evidence only.

    Keyword fallback evidence is intentionally retained for training continuity, but
    it cannot produce a formal overall score. A real structured semantic provider
    must replace it before automatic clinical conclusions are enabled.
    """
    contract = dialogue.contract_snapshot
    turns = list(db.scalars(select(ScenarioDialogueTurn).where(ScenarioDialogueTurn.dialogue_session_id == dialogue.id)))
    patient_turns = [turn for turn in turns if turn.speaker == DialogueSpeaker.patient]
    units = [item for item in contract.get("required_information_units", []) if isinstance(item, dict)]
    evidence = [item for turn in patient_turns for item in (turn.semantic_evidence or {}).get("information_units", [])]
    collected = {str(item.get("id")) for item in evidence if item.get("id")}
    required = {str(item) for item in contract.get("goal_requirements", []) if isinstance(item, str)}
    information = round(100 * len({item.get("id") for item in units if item.get("id") in collected}) / max(1, len(units)), 1)
    achieved = bool(required and required.issubset(collected))
    goal_status = "achieved" if achieved else ("partly_achieved" if collected else "not_achieved")
    goal_score = config_value("scenario_dialogue_goal_scores")[goal_status]
    response_turns = [
        turn
        for turn in patient_turns
        if (turn.semantic_evidence or {}).get("answered_current_question")
        or (turn.semantic_evidence or {}).get("information_units")
    ]
    relevant_turns = [
        turn
        for turn in patient_turns
        if (turn.semantic_evidence or {}).get("relevance") == "relevant"
        or (turn.semantic_evidence or {}).get("information_units")
    ]
    response = round(100 * len(response_turns) / max(1, len(patient_turns)), 1)
    relevance = round(100 * len(relevant_turns) / max(1, len(patient_turns)), 1)
    independence_penalties = config_value("scenario_dialogue_independence_penalties")
    independence = max(
        0.0,
        100.0
        - dialogue.maximum_prompt_level * independence_penalties["maximum_prompt_level"]
        - dialogue.prompt_count * independence_penalties["prompt_count"],
    )
    repair_score = _repair_score(turns)
    required_evidence = [item for item in evidence if item.get("id") in required]
    confidence_min = config_value("scenario_dialogue_evidence_confidence_min")
    low_confidence = any(
        not isinstance(item.get("confidence"), (int, float)) or item["confidence"] < confidence_min
        for item in required_evidence
    )
    fallback_used = any((turn.semantic_evidence or {}).get("source") != "llm_structured" for turn in patient_turns)
    mock_asr_used = any(turn.asr_provider == "mock" for turn in patient_turns)
    trusted = bool(required_evidence) and not fallback_used and not mock_asr_used and not low_confidence
    review_status = "pending_clinician_review" if trusted else "pending_semantic_review"
    confidence = min((float(item.get("confidence", 0)) for item in required_evidence), default=0.0) if trusted else 0.0
    weights = config_value("scenario_dialogue_score_weights")
    overall = None if not trusted else round(
        goal_score * weights["goal"]
        + information * weights["information"]
        + response * weights["response"]
        + relevance * weights["relevance"]
        + independence * weights["independence"]
        + (repair_score or 0) * weights["repair"],
        1,
    )
    return ScenarioDialogueEvaluation(
        dialogue_session_id=dialogue.id, goal_status=goal_status, goal_score=goal_score,
        information_score=information, response_score=response, relevance_score=relevance,
        independence_score=independence, repair_score=repair_score, overall_score=overall,
        confidence=confidence, review_status=review_status, scoring_version="scenario-dialogue-rules-v2",
        evidence_snapshot={
            "collected_information_unit_ids": sorted(collected),
            "required_information_unit_ids": sorted(required),
            "patient_turn_count": len(patient_turns),
            "fallback_used": fallback_used,
            "mock_asr_used": mock_asr_used,
            "low_confidence": low_confidence,
            "unanswered_current_question_count": sum(
                1 for turn in patient_turns if (turn.semantic_evidence or {}).get("answered_current_question") is False
            ),
            "policy_actions": [
                (turn.semantic_evidence or {}).get("policy_action")
                for turn in turns
                if (turn.semantic_evidence or {}).get("policy_action")
            ],
        },
    )


def _repair_score(turns: list[ScenarioDialogueTurn]) -> float | None:
    """Score only the immediate response to a real repair opportunity."""
    repair_indexes = [index for index, turn in enumerate(turns) if turn.speaker == DialogueSpeaker.agent and turn.dialogue_act == "repair"]
    if not repair_indexes:
        return None
    outcomes = []
    for index in repair_indexes:
        response_turn = next((turn for turn in turns[index + 1 :] if turn.speaker == DialogueSpeaker.patient), None)
        if response_turn is None:
            outcomes.append(0.0)
            continue
        evidence = response_turn.semantic_evidence or {}
        outcomes.append(100.0 if evidence.get("information_units") or evidence.get("answered_current_question") else 0.0)
    return round(sum(outcomes) / len(outcomes), 1)
