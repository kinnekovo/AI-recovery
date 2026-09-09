"""Constrained semantic extraction for multi-turn scenario dialogue.

This adapter deliberately does not score or generate feedback. It returns evidence
only, and callers must reject anything that cannot be located in the patient's
transcript.
"""
import json

import httpx

from app.core.config import get_settings


PROMPT_VERSION = "scenario-semantic-evidence-v1"
ROLE_REPLY_PROMPT_VERSION = "scenario-role-reply-v2"


def extract_evidence(contract: dict, transcript: str) -> dict | None:
    settings = get_settings()
    if settings.llm_feedback_provider not in {"openai", "openai_compatible", "external"}:
        return None
    if not settings.llm_feedback_api_key or not settings.llm_feedback_base_url or not settings.llm_feedback_model:
        return None
    units = [item for item in contract.get("required_information_units", []) + contract.get("optional_information_units", []) if isinstance(item, dict)]
    payload = {
        "model": settings.llm_feedback_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是康复训练中的语义证据抽取器。只返回 JSON，不评分，不诊断。每个 supported 信息单元必须逐字引用患者原话；不确定时标 uncertain。"},
            {"role": "user", "content": json.dumps({"task": "从患者本轮表达中提取下列沟通信息单元", "information_units": [{"id": item.get("id"), "label": item.get("label")} for item in units], "patient_transcript": transcript, "required_output": {"information_units": [{"id": "unit id", "status": "supported|uncertain|absent", "quote": "患者原话", "confidence": "0..1"}], "answered_current_question": "boolean", "relevance": "relevant|uncertain|irrelevant"}}, ensure_ascii=False)},
        ],
    }
    url = settings.llm_feedback_base_url.rstrip("/") + "/chat/completions"
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {settings.llm_feedback_api_key}"}, json=payload, timeout=15)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None
    except Exception:
        return None
    return _validate(parsed, transcript, {str(item.get("id")) for item in units})


def _validate(value: object, transcript: str, allowed_ids: set[str]) -> dict | None:
    if not isinstance(value, dict) or not isinstance(value.get("information_units"), list):
        return None
    accepted = []
    for item in value["information_units"]:
        if not isinstance(item, dict) or item.get("id") not in allowed_ids or item.get("status") != "supported":
            continue
        quote = item.get("quote")
        confidence = item.get("confidence")
        if not isinstance(quote, str) or not quote or quote not in transcript or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            return None
        accepted.append({"id": item["id"], "quote": quote, "confidence": float(confidence)})
    return {"source": "llm_structured", "prompt_version": PROMPT_VERSION, "information_units": accepted, "answered_current_question": bool(value.get("answered_current_question")), "relevance": value.get("relevance", "uncertain")}


def generate_role_reply(
    contract: dict,
    dialogue_act: str,
    fallback_reply: str,
    *,
    conversation_history: list[dict] | None = None,
    current_patient_utterance: str | None = None,
    target_information_unit: dict | None = None,
    collected_information_unit_ids: list[str] | None = None,
) -> str | None:
    """Generate contextual wording while the deterministic state machine owns the action.

    The model sees the whole bounded dialogue (a scenario has at most five patient
    turns), but it cannot choose whether to clarify, repair, complete, or escalate.
    It must echo the action and target selected by the rule layer; otherwise the
    response is discarded and the authored fallback is used.
    """
    settings = get_settings()
    if settings.llm_feedback_provider not in {"openai", "openai_compatible", "external"} or not all((settings.llm_feedback_api_key, settings.llm_feedback_base_url, settings.llm_feedback_model)):
        return None
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
        response = httpx.post(settings.llm_feedback_base_url.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {settings.llm_feedback_api_key}"}, json=payload, timeout=15)
        response.raise_for_status()
        parsed = json.loads(response.json()["choices"][0]["message"]["content"])
        if parsed.get("dialogue_act") != dialogue_act or str(parsed.get("target_information_unit_id") or "") != target_id:
            return None
        reply = parsed.get("reply")
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None
    except Exception:
        return None
    if (
        not isinstance(reply, str)
        or not reply.strip()
        or len(reply.strip()) > 45
        or reply.count("？") + reply.count("?") > 1
        or any(term in reply for term in ("诊断", "处方", "服用", "剂量", "你说错", "回答错误"))
    ):
        return None
    return reply.strip()
