"""Pure Policy V2 shadow engine. Input must be Profile V2's consumer contract."""
from __future__ import annotations
from datetime import datetime, timezone
from .rules import PROFILE_INPUT_POLICY, PRIORITY_ORDER, POLICY_VERSION, RULES_VERSION

def _age_hours(value, now):
    if not value:return None
    if isinstance(value,str): value=datetime.fromisoformat(value.replace("Z","+00:00"))
    return (now-value).total_seconds()/3600

def decide(profile: dict|None, *, now: datetime|None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    base={"policy_version":POLICY_VERSION,"rules_version":RULES_VERSION,"mode":"shadow","generated_at":now.isoformat(),"training_focus":[],"warnings":[],"reason_codes":[]}
    if not profile:
        return {**base,"input_status":"insufficient_profile","status":"generated","training_focus":[],"difficulty":{"recommended_difficulty_action":"insufficient_evidence","reason_codes":["NO_PROFILE"]},"reassessment":{"signal":"insufficient_evidence","reason_codes":["NO_PROFILE"]},"reason_codes":["NO_PROFILE"]}
    if profile.get("profile_failure") or profile.get("status") == "failed":
        return _blocked(base, "profile_refresh_required", "PROFILE_BUILD_FAILED", "insufficient_evidence")
    age=_age_hours(profile.get("generated_at"),now); dimensions=profile.get("dimensions") or []
    if age is not None and age>PROFILE_INPUT_POLICY["review_max_hours"]:
        return _blocked(base, "insufficient_input", "PROFILE_STALE", "insufficient_evidence")
    if age is not None and age>PROFILE_INPUT_POLICY["fresh_max_hours"]:
        return _blocked(base, "review_required", "PROFILE_STALE", "review_required")
    if profile.get("status") in {"review_required","insufficient"} or len(dimensions)<PROFILE_INPUT_POLICY["minimum_sufficient_dimensions"]:
        return _blocked(base,"insufficient_input","INSUFFICIENT_PROFILE_EVIDENCE","insufficient_evidence")
    focus=[]
    for dim in dimensions:
        trend=dim.get("trend","insufficient"); state=dim.get("current_state")
        if trend=="falling": priority,reasons="high",["FALLING_TREND"]
        elif state=="low": priority,reasons="medium",["LOW_CURRENT_STATE"]
        elif trend=="mixed": priority,reasons="medium",["MIXED_TREND_REVIEW"]
        elif trend=="rising": priority,reasons="low",["RISING_TREND"]
        elif trend=="stable": priority,reasons="low",["STABLE_STATE"]
        else: priority,reasons="not_eligible",["TREND_INSUFFICIENT"]
        focus.append({"dimension_code":dim.get("code"),"priority":priority,"confidence_state":dim.get("evidence_sufficiency"),"profile_state":{"current_value":dim.get("current_value"),"unit":dim.get("unit"),"trend":trend},"reason_codes":reasons})
    focus.sort(key=lambda x:(PRIORITY_ORDER[x["priority"]],x["dimension_code"] or ""))
    actionable=[x for x in focus if x["priority"]!="not_eligible"]
    if any(x["profile_state"]["trend"]=="falling" for x in actionable): difficulty={"recommended_difficulty_action":"decrease","reason_codes":["FALLING_PROFILE_TREND"],"difficulty_system":"legacy L/S referenced only; not applied"}
    elif any(x["profile_state"]["trend"]=="mixed" for x in actionable): difficulty={"recommended_difficulty_action":"review_required","reason_codes":["MIXED_PROFILE_TREND"],"difficulty_system":"legacy L/S referenced only; not applied"}
    elif actionable and all(x["profile_state"]["trend"]=="rising" for x in actionable): difficulty={"recommended_difficulty_action":"increase","reason_codes":["RISING_PROFILE_TRENDS"],"difficulty_system":"legacy L/S referenced only; not applied"}
    else: difficulty={"recommended_difficulty_action":"maintain","reason_codes":["NO_CHANGE_SIGNAL"],"difficulty_system":"legacy L/S referenced only; not applied"}
    reassessment={"signal":"no_signal","reason_codes":["PROFILE_FRESH"]}
    clinical=profile.get("latest_clinical_assessment_at")
    if clinical and _age_hours(clinical,now)>PROFILE_INPUT_POLICY["long_assessment_interval_days"]*24: reassessment={"signal":"consider_reassessment","reason_codes":["LONG_INTERVAL_SINCE_CLINICAL_ASSESSMENT"]}
    reasons=sorted({code for item in actionable for code in item["reason_codes"]}|set(difficulty["reason_codes"])|set(reassessment["reason_codes"]))
    return {**base,"input_status":"eligible","status":"generated","training_focus":focus,"difficulty":difficulty,"reassessment":reassessment,"reason_codes":reasons}

def _blocked(base,input_status,reason,action):
    return {**base,"input_status":input_status,"status":"generated","training_focus":[],"difficulty":{"recommended_difficulty_action":action,"reason_codes":[reason]},"reassessment":{"signal":"review_required" if action=="review_required" else "insufficient_evidence","reason_codes":[reason]},"warnings":[reason],"reason_codes":[reason]}
