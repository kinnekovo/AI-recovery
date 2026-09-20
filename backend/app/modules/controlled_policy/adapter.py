"""Maps a policy suggestion onto existing session-task fields only."""
from __future__ import annotations
from app.modules.controlled_policy.policy import MAX_DIFFICULTY_DELTA, MAX_PROMPT_LEVEL, MIN_PROMPT_LEVEL, SCOPE
from app.modules.training.model import TrainingType

def _dimension_training_type(dimension_code: str) -> TrainingType | None:
    prefix = (dimension_code or "").split(".", 1)[0]
    return TrainingType(prefix) if prefix in {item.value for item in TrainingType} else None

def focus_preview(session, dimension_code: str) -> tuple[dict, dict]:
    kind = _dimension_training_type(dimension_code)
    if not kind:
        raise ValueError("no_supported_training_target")
    tasks = list(session.session_tasks)
    target = next((task for task in tasks if task.task_template.task_type == kind), None)
    if not target:
        raise ValueError("no_supported_training_target")
    before = {str(task.id): task.order_index for task in tasks}
    after = dict(before)
    for task in tasks:
        if task.id == target.id:
            after[str(task.id)] = 0
        elif task.order_index < target.order_index:
            after[str(task.id)] = task.order_index + 1
    return ({"dimension_code": dimension_code, "task_id": str(target.id), "order_indexes": after},
            {"order_indexes": before})

def difficulty_preview(session, requested_delta: int) -> tuple[dict, dict]:
    if requested_delta not in {-MAX_DIFFICULTY_DELTA, MAX_DIFFICULTY_DELTA}:
        raise ValueError("unsupported_difficulty_delta")
    tasks = list(session.session_tasks)
    if not tasks:
        raise ValueError("no_supported_training_target")
    target = min(tasks, key=lambda item: item.order_index)
    # Higher difficulty means one less prompt; lower difficulty means one more.
    next_level = max(MIN_PROMPT_LEVEL, min(MAX_PROMPT_LEVEL, target.prompt_level - requested_delta))
    return ({"task_id": str(target.id), "requested_difficulty_delta": requested_delta,
             "prompt_level": next_level, "no_op": next_level == target.prompt_level},
            {"prompt_level": target.prompt_level})

def proposal_preview(session, action_type: str, value) -> tuple[dict, dict, dict]:
    if action_type == "training_focus_override":
        proposed, current = focus_preview(session, str(value))
    elif action_type == "difficulty_step_adjustment":
        proposed, current = difficulty_preview(session, int(value))
    else:
        raise ValueError("unsupported_action")
    return proposed, current, {"scope": SCOPE, "training_session_id": str(session.id)}

def apply_to_session(session, action_type: str, proposed_value: dict) -> tuple[dict, dict, bool]:
    if action_type == "training_focus_override":
        expected = proposed_value["order_indexes"]
        before = {"order_indexes": {str(task.id): task.order_index for task in session.session_tasks}}
        changed = False
        for task in session.session_tasks:
            wanted = int(expected[str(task.id)])
            changed = changed or task.order_index != wanted
            task.order_index = wanted
        return before, {"order_indexes": expected}, changed
    if action_type == "difficulty_step_adjustment":
        task = next((item for item in session.session_tasks if str(item.id) == proposed_value["task_id"]), None)
        if not task:
            raise ValueError("state_conflict")
        before = {"prompt_level": task.prompt_level}
        wanted = int(proposed_value["prompt_level"])
        # A proposed no-op is allowed, but a changed precondition is not.
        expected_current = wanted + int(proposed_value["requested_difficulty_delta"])
        if not proposed_value.get("no_op") and task.prompt_level != expected_current:
            raise ValueError("state_conflict")
        task.prompt_level = wanted
        return before, {"prompt_level": wanted}, before["prompt_level"] != wanted
    raise ValueError("unsupported_action")
