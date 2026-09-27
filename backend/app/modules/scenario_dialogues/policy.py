"""Deterministic policy for functional scenario conversations.

The semantic model may describe what the patient said, but this module owns the
next action. Keeping the policy deterministic prevents an LLM from skipping a
required communication goal or asking an optional question before its
prerequisites are known.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DialoguePolicyDecision:
    action: str
    state: str
    target: dict[str, Any] | None = None
    reason: str = ""
    should_complete: bool = False


def contract_units(contract: dict) -> list[dict[str, Any]]:
    """Return the de-duplicated unit catalogue in authored order."""
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("required_information_units", "optional_information_units"):
        for unit in contract.get(key, []) or []:
            if not isinstance(unit, dict) or not unit.get("id"):
                continue
            unit_id = str(unit["id"])
            if unit_id in seen:
                continue
            seen.add(unit_id)
            units.append(unit)
    return units


def unit_by_id(contract: dict, unit_id: str | None) -> dict[str, Any] | None:
    if not unit_id:
        return None
    return next((unit for unit in contract_units(contract) if str(unit.get("id")) == str(unit_id)), None)


def effective_required_ids(contract: dict) -> list[str]:
    """Use the explicit product goal, while tolerating malformed old contracts."""
    configured = [item for item in contract.get("goal_requirements", []) or [] if isinstance(item, str) and item]
    known = {str(unit.get("id")) for unit in contract_units(contract)}
    return [item for item in configured if item in known]


def _priority(contract: dict, unit: dict[str, Any]) -> tuple[int, int]:
    priorities = contract.get("question_priority") or []
    unit_id = str(unit.get("id"))
    try:
        authored = priorities.index(unit_id)
    except (ValueError, AttributeError):
        authored = len(priorities)
    authored_order = next((index for index, candidate in enumerate(contract_units(contract)) if candidate.get("id") == unit_id), 0)
    return authored, authored_order


def _dependencies_satisfied(unit: dict[str, Any], collected: set[str]) -> bool:
    dependencies = unit.get("depends_on") or unit.get("requires") or []
    if not isinstance(dependencies, list):
        return True
    return all(str(item) in collected for item in dependencies if isinstance(item, str))


def _optional_target(contract: dict, collected: set[str]) -> dict[str, Any] | None:
    """Select optional context only when the scenario explicitly asks for it."""
    policy = contract.get("optional_follow_up_policy")
    for unit in contract.get("optional_information_units", []) or []:
        if not isinstance(unit, dict) or not unit.get("id"):
            continue
        if str(unit["id"]) in collected or not _dependencies_satisfied(unit, collected):
            continue
        if policy == "always_before_completion" or unit.get("prompt_when_missing") is True:
            return unit
    return None


def choose_dialogue_action(
    contract: dict,
    *,
    collected: set[str],
    patient_turn_count: int,
    minimum_patient_turns: int,
    maximum_patient_turns: int,
    current_target_id: str | None = None,
    answered_current_question: bool | None = None,
    answer_status: str | None = None,
    repair_already_offered: bool = False,
) -> DialoguePolicyDecision:
    """Choose the next safe action from the validated conversation state."""
    required_ids = effective_required_ids(contract)
    missing_required = [
        unit
        for unit in contract_units(contract)
        if str(unit.get("id")) in required_ids and str(unit.get("id")) not in collected
    ]
    missing_required.sort(key=lambda unit: _priority(contract, unit))

    current_target = unit_by_id(contract, current_target_id)
    unresolved_current = (
        current_target is not None
        and answered_current_question is False
        and answer_status not in {"supported", "confirmed"}
    )
    if unresolved_current:
        return DialoguePolicyDecision(
            action="clarify_current",
            state="clarifying",
            target=current_target,
            reason="患者本轮没有回答工作人员上一轮追问。",
        )

    if missing_required:
        return DialoguePolicyDecision(
            action="acknowledge_and_ask" if collected else "ask_required",
            state="clarifying",
            target=missing_required[0],
            reason="先承接患者已经提供的信息，再追问仍缺失的场景目标。" if collected else "仍有场景目标信息未收集。",
        )

    if (
        contract.get("repair_opportunities")
        and patient_turn_count >= minimum_patient_turns
        and not repair_already_offered
    ):
        return DialoguePolicyDecision(
            action="repair",
            state="repairing",
            reason="场景配置要求在完成目标后进行一次修复确认。",
        )

    optional_target = _optional_target(contract, collected)
    if optional_target is not None:
        return DialoguePolicyDecision(
            action="ask_optional",
            state="confirming",
            target=optional_target,
            reason="可选信息已满足前置条件，且场景明确要求补充。",
        )

    if patient_turn_count < minimum_patient_turns:
        return DialoguePolicyDecision(
            action="confirm",
            state="confirming",
            reason="核心目标已满足，但仍需一次确认回合。",
        )

    if patient_turn_count >= maximum_patient_turns:
        return DialoguePolicyDecision(
            action="close",
            state="turn_limit_reached",
            reason="已达到场景最大患者回合数。",
            should_complete=True,
        )

    return DialoguePolicyDecision(
        action="complete",
        state="completed",
        reason="所有必要目标信息均已明确，且没有待处理的条件性追问。",
        should_complete=True,
    )
