"""Deterministic engineering rules for shadow observation; no clinical claims."""
POLICY_VERSION="policy-v2.0"
RULES_VERSION="policy-rules-v1"
PROFILE_INPUT_POLICY_VERSION="policy-profile-input-policy-v1"
PROFILE_INPUT_POLICY={"fresh_max_hours":24,"review_max_hours":168,"minimum_sufficient_dimensions":1,"long_assessment_interval_days":180,"source":"engineering_observation_policy","maturity":"E1"}
PRIORITY_ORDER={"high":0,"medium":1,"low":2,"not_eligible":3}
