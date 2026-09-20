SCHEMA_VERSION = "controlled-governance-v1"
EVALUATION_POLICY_VERSION = "controlled-evaluation-policy-v1"
GOVERNANCE_POLICY_VERSION = "controlled-governance-policy-v1"
STATUSES = {"insufficient_evidence", "controlled", "review_required", "eligible_for_streamlined_evaluation", "manual_only", "suspended"}
REJECTION_REASONS = {"wrong_training_focus", "difficulty_change_not_appropriate", "insufficient_context", "patient_state_changed", "manual_plan_preferred", "proposal_stale", "training_target_unavailable", "conflicting_clinical_judgment", "other"}
ROLLBACK_REASONS = {"therapist_changed_mind", "patient_session_context_changed", "unexpected_training_behavior", "incorrect_mapping", "difficulty_not_suitable", "focus_not_suitable", "technical_issue", "other"}
POLICY = {"version": GOVERNANCE_POLICY_VERSION, "minimum_proposals": 3, "minimum_approved": 2, "minimum_applied": 2,
 "minimum_unique_patients": 2, "minimum_unique_therapists": 1, "minimum_observed_sessions": 1,
 "maximum_rollback_rate": .5, "maximum_apply_failure_rate": .5, "maximum_state_conflict_rate": .5,
 "maximum_safety_block_rate": .5, "maximum_material_override_rate": .5, "minimum_session_completion_coverage": .3,
 "source": "internal engineering governance thresholds; not clinical standards", "maturity": "E1"}
