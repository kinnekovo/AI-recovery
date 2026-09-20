export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

export interface PatientProfileProjection {
  snapshot_id?: string
  status: string
  freshness: string
  dimensions: PatientProfileDimension[]
  limitations: string[]
}

export interface PatientProfileDimension {
  code: string
  status: string
  trend: string
  evidence_sufficiency: string | number | null
}

export interface ProfileSnapshot {
  id: string
  patient_profile_id: string
  profile_schema_version: string
  mapping_version: string
  evidence_policy_version: string
  generated_at: string
  as_of: string | null
  status: string
  previous_snapshot_id: string | null
  evidence_fingerprint: string
  payload: JsonObject
}

export interface ProfileEvidence {
  id: string
  snapshot_id: string
  evaluation_run_id: string
  source_type: string
  source_id: string
  profile_dimension_code: string
  source_dimension_code: string
  source_kind: string
  unit: string | null
  metric_status: string | null
  canonical_result_status: string
  evidence_timestamp: string
  metadata_snapshot: JsonObject
}

export interface ClinicalStageDetail {
  assessment: JsonObject
  source: JsonObject
  canonical_preview: JsonObject
  canonical_result?: JsonObject | null
  comparability?: JsonObject | null
  warnings?: string[]
  [key: string]: JsonValue | undefined
}

export interface ComparabilityResult {
  status?: string
  reason_codes?: string[]
  dimensions?: JsonValue[]
  [key: string]: JsonValue | undefined
}

export interface PolicyDecision {
  id: string
  patient_profile_id: string
  profile_snapshot_id: string | null
  policy_version: string
  rules_version: string
  mode: string
  generated_at: string
  status: string
  input_fingerprint: string
  decision_payload: JsonObject
  reason_codes: string[]
  warnings: string[]
}

export interface PolicyExplanation {
  decision_id?: string
  rules?: JsonValue[]
  reason_codes?: string[]
  [key: string]: JsonValue | undefined
}

export interface ControlledProposal {
  id: string
  policy_decision_id: string
  patient_profile_id: string
  target_training_session_id: string
  action_type: 'training_focus_override' | 'difficulty_step_adjustment'
  proposed_value: JsonObject
  current_value: JsonObject
  expected_scope: JsonObject
  reason_codes: string[]
  policy_version: string
  rules_version: string
  validation_run_id: string | null
  profile_snapshot_id: string | null
  activation_policy_version: string
  status: string
  expires_at: string
  created_at: string
  execution_id?: string | null
}

export interface ControlledAuditItem {
  event_type?: string
  status?: string
  actor_user_id?: string | null
  created_at?: string
  [key: string]: JsonValue | undefined
}
export interface ControlledHistory { proposals: ControlledProposal[]; analytics: JsonObject }

export interface CalibrationDataset {
  id: string
  name: string
  version: string
  status: string
  frozen_at: string | null
  sample_count: number
  sample_ids: string[]
}

export interface CalibrationRunResult { id: string; decision: string; reason_codes: string[] }
export interface CalibrationReport { run_id: string; dataset: JsonObject; metric: JsonObject; split: JsonObject; policy: JsonObject; development: JsonObject; holdout: JsonObject; subgroups: JsonObject; human_reference_quality: JsonObject; promotion: JsonObject; limitations: string[] }
export interface MetricRegistry { metric_code: string; status: string; version: string; last_calibrated_at: string | null; calibration_runs: Array<{ id: string; decision: string; reasons: string[] }> }

export interface RegistryEntry { policy_version: string; rules_version: string; action_type?: string; validation_status?: string; governance_status?: string; reason_codes: string[]; latest_run_id?: string | null; latest_validation_run_id?: string | null; validated_at?: string | null }
export interface GovernanceRun { id: string; status: string; reason_codes: string[]; report: JsonObject }
