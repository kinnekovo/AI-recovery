"""Versioned engineering guardrails for controlled activation, not clinical rules."""
from datetime import timedelta

VERSION = "controlled-activation-policy-v1"
ALLOWED_ACTION_TYPES = {"training_focus_override", "difficulty_step_adjustment"}
ELIGIBLE_VALIDATION_STATUSES = {"eligible_for_controlled_activation"}
MAX_DIFFICULTY_DELTA = 1
MIN_PROMPT_LEVEL = 0
MAX_PROMPT_LEVEL = 3
APPROVAL_VALIDITY = timedelta(hours=24)
PROPOSAL_VALIDITY = timedelta(hours=24)
SCOPE = "specific_training_session"
POLICY = {
    "version": VERSION,
    "eligible_validation_statuses": sorted(ELIGIBLE_VALIDATION_STATUSES),
    "allowed_action_types": sorted(ALLOWED_ACTION_TYPES),
    "max_difficulty_delta": MAX_DIFFICULTY_DELTA,
    "approval_validity_hours": 24,
    "proposal_validity_hours": 24,
    "scope": SCOPE,
    "concurrent_action_behavior": "one_effective_proposal_per_patient_session_action_type",
    "rollback": "therapist_explicit_only",
    "source": "engineering safety policy",
    "maturity": "E1",
}
