"""Constrained semantic extraction for multi-turn scenario dialogue.

This adapter deliberately does not score or generate feedback. It returns evidence
only, and callers must reject anything that cannot be located in the patient's
transcript.
"""
import json
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.observability import log_event


PROMPT_VERSION = "scenario-semantic-evidence-v3"
ROLE_REPLY_PROMPT_VERSION = "scenario-role-reply-v3"


@dataclass(frozen=True)
class LLMCallResult:
    """A bounded provider result used for fallback and operational evidence."""

    value: dict | str | None
    status: str
    error_code: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None


_SUPPORTED_PROVIDERS = {"openai", "openai_compatible", "external"}
_RETRYABLE_HTTP_STATUS_CODES = {429, 502, 503, 504}


def _retry_delay_seconds(response: httpx.Response | None, backoff_seconds: float, attempt: int) -> float:
    """Return a bounded provider-directed or exponential retry delay."""
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 5.0)
            except ValueError:
                pass
    return min(backoff_seconds * (2 ** max(attempt - 1, 0)), 5.0)


def _post_chat_completion(settings, operation: str, payload: dict, started: float) -> tuple[httpx.Response | None, LLMCallResult | None]:
    """Call an OpenAI-compatible endpoint with bounded transient retries.

    Permanent client/configuration failures fail immediately. This keeps the
    training path responsive while allowing a briefly overloaded gateway to
    recover without silently dropping straight to authored fallback copy.
    """
    timeout_seconds = float(getattr(settings, "llm_feedback_timeout_seconds", 8.0))
    max_attempts = int(getattr(settings, "llm_feedback_max_attempts", 3))
    backoff_seconds = float(getattr(settings, "llm_feedback_retry_backoff_seconds", 0.6))
    url = settings.llm_feedback_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_feedback_api_key}"}

    for attempt in range(1, max_attempts + 1):
        response: httpx.Response | None = None
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            status_code = int(getattr(response, "status_code", 200))
            if status_code in _RETRYABLE_HTTP_STATUS_CODES and attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(response, backoff_seconds, attempt)
                log_event(
                    "warning",
                    "llm",
                    "scenario_llm_retrying",
                    operation=operation,
                    provider=getattr(settings, "llm_feedback_provider", None),
                    model=getattr(settings, "llm_feedback_model", None),
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    http_status_code=status_code,
                    delay_seconds=delay_seconds,
                )
                if delay_seconds:
                    time.sleep(delay_seconds)
                continue
            response.raise_for_status()
            return response, None
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            return None, _failure_result(
                settings,
                operation,
                "http_error",
                f"http_status_{status_code}",
                started,
                error,
                attempts=attempt,
                http_status_code=status_code,
            )
        except httpx.TransportError as error:
            if attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(None, backoff_seconds, attempt)
                log_event(
                    "warning",
                    "llm",
                    "scenario_llm_retrying",
                    operation=operation,
                    provider=getattr(settings, "llm_feedback_provider", None),
                    model=getattr(settings, "llm_feedback_model", None),
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    transport_error=type(error).__name__,
                    delay_seconds=delay_seconds,
                )
                if delay_seconds:
                    time.sleep(delay_seconds)
                continue
            error_code = "request_timeout" if isinstance(error, httpx.TimeoutException) else "transport_error"
            return None, _failure_result(
                settings,
                operation,
                "http_error",
                error_code,
                started,
                error,
                attempts=attempt,
            )
    return None, _failure_result(settings, operation, "provider_error", "retry_loop_exhausted", started)


def _not_ready_result(settings, operation: str) -> LLMCallResult | None:
    provider = getattr(settings, "llm_feedback_provider", None)
    model = getattr(settings, "llm_feedback_model", None)
    if provider not in _SUPPORTED_PROVIDERS:
        status = "disabled"
        error_code = "provider_disabled"
    elif not all((getattr(settings, "llm_feedback_api_key", None), getattr(settings, "llm_feedback_base_url", None), model)):
        status = "not_configured"
        error_code = "missing_provider_config"
    else:
        return None
    log_event("info", "llm", "scenario_llm_not_called", operation=operation, status=status, error_code=error_code, provider=provider, model=model)
    return LLMCallResult(None, status, error_code, provider, model, 0)


def _failure_result(
    settings,
    operation: str,
    status: str,
    error_code: str,
    started: float,
    error: BaseException | None = None,
    **details,
) -> LLMCallResult:
    provider = getattr(settings, "llm_feedback_provider", None)
    model = getattr(settings, "llm_feedback_model", None)
    latency_ms = int((time.monotonic() - started) * 1000)
    fields = {"operation": operation, "status": status, "error_code": error_code, "provider": provider, "model": model, "latency_ms": latency_ms}
    if error is not None:
        fields["error"] = error
    fields.update(details)
    log_event("warning", "llm", "scenario_llm_failed", **fields)
    return LLMCallResult(None, status, error_code, provider, model, latency_ms)


def _success_result(settings, operation: str, value: dict | str, started: float) -> LLMCallResult:
    provider = getattr(settings, "llm_feedback_provider", None)
    model = getattr(settings, "llm_feedback_model", None)
    latency_ms = int((time.monotonic() - started) * 1000)
    log_event("info", "llm", "scenario_llm_succeeded", operation=operation, status="success", provider=provider, model=model, latency_ms=latency_ms)
    return LLMCallResult(value, "success", None, provider, model, latency_ms)


def extract_evidence(
    contract: dict,
    transcript: str,
    *,
    last_agent_question: str | None = None,
    current_target_information_unit: dict | None = None,
    conversation_history: list[dict] | None = None,
    collected_information_unit_ids: list[str] | None = None,
) -> dict | None:
    return extract_evidence_with_status(
        contract,
        transcript,
        last_agent_question=last_agent_question,
        current_target_information_unit=current_target_information_unit,
        conversation_history=conversation_history,
        collected_information_unit_ids=collected_information_unit_ids,
    ).value


def extract_evidence_with_status(
    contract: dict,
    transcript: str,
    *,
    last_agent_question: str | None = None,
    current_target_information_unit: dict | None = None,
    conversation_history: list[dict] | None = None,
    collected_information_unit_ids: list[str] | None = None,
) -> LLMCallResult:
    settings = get_settings()
    not_ready = _not_ready_result(settings, "semantic_extraction")
    if not_ready is not None:
        return not_ready
    started = time.monotonic()
    units = [item for item in contract.get("required_information_units", []) + contract.get("optional_information_units", []) if isinstance(item, dict)]
    context = {
        "last_agent_question": last_agent_question or "",
        "current_target_information_unit": current_target_information_unit or {},
        "conversation_history": conversation_history or [],
        "collected_information_unit_ids": collected_information_unit_ids or [],
    }
    payload = {
        "model": settings.llm_feedback_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是康复训练中的多轮场景语义解析器。只返回 JSON，不评分，不诊断。必须区分患者是否回答了工作人员上一句话。每个 supported 信息单元必须逐字引用患者原话；不确定时标 uncertain；不得凭空补全信息。"},
            {"role": "user", "content": json.dumps({
                "task": "结合对话上下文解析患者本轮表达，并提取可验证的信息单元",
                "context": context,
                "information_units": [{"id": item.get("id"), "label": item.get("label"), "depends_on": item.get("depends_on", [])} for item in units],
                "patient_transcript": transcript,
                "required_output": {
                    "dialogue_act": "answer|provide_information|clarify|irrelevant|refusal|repair|urgent",
                    "answered_target_id": "当前问题对应的信息单元 id 或 null",
                    "answer_status": "supported|uncertain|contradicted|absent",
                    "information_units": [{"id": "unit id", "status": "supported|uncertain|contradicted|absent", "quote": "患者原话（如有）", "confidence": "0..1"}],
                    "answered_current_question": "boolean",
                    "relevance": "relevant|uncertain|irrelevant",
                    "contradictions": "string array",
                },
            }, ensure_ascii=False)},
        ],
    }
    try:
        response, failure = _post_chat_completion(settings, "semantic_extraction", payload, started)
        if failure is not None:
            return failure
        assert response is not None
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, TypeError) as error:
        return _failure_result(settings, "semantic_extraction", "invalid_response", "response_shape_invalid", started, error)
    except (ValueError, json.JSONDecodeError) as error:
        return _failure_result(settings, "semantic_extraction", "invalid_json", "response_json_invalid", started, error)
    except Exception as error:
        return _failure_result(settings, "semantic_extraction", "provider_error", "unexpected_provider_error", started, error)
    validated = _validate(
        parsed,
        transcript,
        {str(item.get("id")) for item in units},
        current_target_id=str((current_target_information_unit or {}).get("id") or "") or None,
    )
    if validated is None:
        return _failure_result(settings, "semantic_extraction", "schema_rejected", "evidence_schema_rejected", started)
    return _success_result(settings, "semantic_extraction", validated, started)


def _validate(
    value: object,
    transcript: str,
    allowed_ids: set[str],
    *,
    current_target_id: str | None = None,
) -> dict | None:
    if not isinstance(value, dict) or not isinstance(value.get("information_units"), list):
        return None
    accepted = []
    unit_statuses = []
    for item in value["information_units"]:
        if not isinstance(item, dict) or item.get("id") not in allowed_ids:
            continue
        item_id = str(item["id"])
        item_status = item.get("status")
        if item_status not in {"supported", "uncertain", "contradicted", "absent"}:
            continue
        quote = item.get("quote")
        confidence = item.get("confidence")
        if quote is not None and (not isinstance(quote, str) or quote not in transcript):
            return None
        if confidence is None and item_status in {"absent", "contradicted"}:
            confidence = 0.0
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            return None
        normalized = {"id": item_id, "status": item_status, "quote": quote or "", "confidence": float(confidence)}
        unit_statuses.append(normalized)
        if item_status == "supported":
            if not quote:
                return None
            accepted.append({"id": item_id, "quote": quote, "confidence": float(confidence)})
    answered_target_id = value.get("answered_target_id")
    if answered_target_id is not None and answered_target_id != "" and answered_target_id not in allowed_ids:
        return None
    answer_status = value.get("answer_status", "uncertain")
    if answer_status not in {"supported", "uncertain", "contradicted", "absent"}:
        answer_status = "uncertain"
    answered_current_question = bool(value.get("answered_current_question"))
    if current_target_id and answered_target_id == current_target_id and answer_status == "supported":
        answered_current_question = True
    dialogue_act = value.get("dialogue_act", "answer")
    if dialogue_act not in {"answer", "provide_information", "clarify", "irrelevant", "refusal", "repair", "urgent"}:
        dialogue_act = "answer"
    relevance = value.get("relevance", "uncertain")
    if relevance not in {"relevant", "uncertain", "irrelevant"}:
        relevance = "uncertain"
    contradictions = value.get("contradictions", [])
    if not isinstance(contradictions, list) or not all(isinstance(item, str) for item in contradictions):
        contradictions = []
    return {
        "source": "llm_structured",
        "prompt_version": PROMPT_VERSION,
        "information_units": accepted,
        "unit_statuses": unit_statuses,
        "answered_current_question": answered_current_question,
        "answered_target_id": answered_target_id,
        "answer_status": answer_status,
        "dialogue_act": dialogue_act,
        "relevance": relevance,
        "contradictions": contradictions,
    }


def generate_role_reply(
    contract: dict,
    dialogue_act: str,
    fallback_reply: str,
    *,
    conversation_history: list[dict] | None = None,
    current_patient_utterance: str | None = None,
    target_information_unit: dict | None = None,
    collected_information_unit_ids: list[str] | None = None,
    acknowledge_evidence: list[dict] | None = None,
) -> str | None:
    return generate_role_reply_with_status(
        contract,
        dialogue_act,
        fallback_reply,
        conversation_history=conversation_history,
        current_patient_utterance=current_patient_utterance,
        target_information_unit=target_information_unit,
        collected_information_unit_ids=collected_information_unit_ids,
        acknowledge_evidence=acknowledge_evidence,
    ).value


def generate_role_reply_with_status(
    contract: dict,
    dialogue_act: str,
    fallback_reply: str,
    *,
    conversation_history: list[dict] | None = None,
    current_patient_utterance: str | None = None,
    target_information_unit: dict | None = None,
    collected_information_unit_ids: list[str] | None = None,
    acknowledge_evidence: list[dict] | None = None,
) -> LLMCallResult:
    """Generate contextual wording while the deterministic state machine owns the action.

    The model sees the whole bounded dialogue (a scenario has at most five patient
    turns), but it cannot choose whether to clarify, repair, complete, or escalate.
    It must echo the action and target selected by the rule layer; otherwise the
    response is discarded and the authored fallback is used.
    """
    settings = get_settings()
    not_ready = _not_ready_result(settings, "role_reply")
    if not_ready is not None:
        return not_ready
    started = time.monotonic()
    target_id = str((target_information_unit or {}).get("id") or "")
    request = {
        "scene": contract.get("scene") or contract.get("display_prompt"),
        "communication_goal": contract.get("communication_goal"),
        "agent_role": contract.get("agent_role", "场景角色"),
        "conversation_history": conversation_history or [],
        "current_patient_utterance": current_patient_utterance or "",
        "collected_information_unit_ids": collected_information_unit_ids or [],
        "locked_dialogue_act": dialogue_act,
        "locked_target_information_unit": target_information_unit or {},
        "acknowledge_evidence": acknowledge_evidence or [],
        "required_meaning": fallback_reply,
        "required_output": {
            "dialogue_act": dialogue_act,
            "target_information_unit_id": target_id,
            "reply": "符合角色、承接上文的一句话",
        },
        "rules": [
            "只输出 JSON，不要解释",
            "reply 不超过45个汉字",
            "必须承接患者本轮原话，避免空泛复述和套话",
            "如果 acknowledge_evidence 非空，先用一句自然短语承接其中与本轮相关的患者信息，再完成 required_meaning",
            "不得改变 locked_dialogue_act",
            "不得改变或新增追问信息目标",
            "澄清时一次只问一个问题，不得提前结束对话",
            "修复时只请求重述或确认当前歧义，不得引入新任务",
            "不诊断、不处方、不提供药物剂量、不评价患者对错",
            "不得虚构地点、价格、预约结果或任何场景事实",
        ],
    }
    payload = {
        "model": settings.llm_feedback_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是言语康复训练中的场景角色回复生成器。规则层已锁定本轮动作和目标；你只能结合完整对话生成自然措辞。",
            },
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ],
    }
    try:
        response, failure = _post_chat_completion(settings, "role_reply", payload, started)
        if failure is not None:
            return failure
        assert response is not None
        parsed = json.loads(response.json()["choices"][0]["message"]["content"])
        if parsed.get("dialogue_act") != dialogue_act or str(parsed.get("target_information_unit_id") or "") != target_id:
            return _failure_result(settings, "role_reply", "schema_rejected", "locked_route_changed", started)
        reply = parsed.get("reply")
    except (KeyError, TypeError) as error:
        return _failure_result(settings, "role_reply", "invalid_response", "response_shape_invalid", started, error)
    except (ValueError, json.JSONDecodeError) as error:
        return _failure_result(settings, "role_reply", "invalid_json", "response_json_invalid", started, error)
    except Exception as error:
        return _failure_result(settings, "role_reply", "provider_error", "unexpected_provider_error", started, error)
    if (
        not isinstance(reply, str)
        or not reply.strip()
        or len(reply.strip()) > 45
        or reply.count("？") + reply.count("?") > 1
        or any(term in reply for term in ("诊断", "处方", "服用", "剂量", "你说错", "回答错误"))
    ):
        return _failure_result(settings, "role_reply", "schema_rejected", "reply_policy_rejected", started)
    return _success_result(settings, "role_reply", reply.strip(), started)
