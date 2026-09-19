"""Deterministic explanation projection; it never invokes an LLM."""
def explain(payload: dict) -> dict:
    return {"policy_version":payload.get("policy_version"),"rules_version":payload.get("rules_version"),
            "input_status":payload.get("input_status"),"reason_codes":payload.get("reason_codes",[]),
            "focus":[{"dimension_code":x.get("dimension_code"),"profile_state":x.get("profile_state"),"reason_codes":x.get("reason_codes",[])} for x in payload.get("training_focus",[])],
            "difficulty":payload.get("difficulty",{}),"reassessment":payload.get("reassessment",{})}
