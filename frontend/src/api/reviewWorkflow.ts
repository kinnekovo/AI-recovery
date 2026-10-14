import { http, request } from './http'

export type AttentionStatus = 'open' | 'acknowledged' | 'in_review' | 'waiting_information' | 'waiting_plan_publish' | 'resolved' | 'dismissed'

export interface ReviewQueueItem {
  id: string
  patient_user_id: string
  patient_profile_id: string
  patient: string
  type: string
  trigger_code: string
  trigger_facts: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
  evidence_ids: string[]
  priority: 'high' | 'normal' | 'low' | string
  summary: string
  status: AttentionStatus
  assigned_to_user_id: string | null
  assigned_to: string | null
  acknowledged_at: string | null
  created_at: string
  status_updated_at: string
  resolved_at: string | null
  resolution_code: string | null
  resolution_note: string | null
  waiting_reason: string | null
  primary_evaluation_run_id: string | null
  primary_stage_review_id: string | null
  evidence_count: number
  next_step: string
}

export interface ReviewQueueResponse {
  summary: { open: number; mine: number; waiting_information: number; waiting_plan_publish: number; total: number }
  items: ReviewQueueItem[]
  next_cursor: string | null
  total: number
}

export interface ReviewDimension {
  id: string
  dimension_code: string
  value: number | null
  level: string | null
  unit: string | null
  status: string
  measurement_quality: Record<string, unknown>
  evidence_snapshot: Record<string, unknown>
  limitations: string[]
}

export interface EvaluationReviewRevision {
  id: string
  evaluation_run_id: string
  dimension_result_id: string | null
  review_action: string
  automatic_value_snapshot: Record<string, unknown>
  revised_value_snapshot: Record<string, unknown>
  evidence_override: Record<string, unknown>
  reason: string | null
  reason_code?: string | null
  reviewer_user_id: string | null
  recomputed_run_id: string | null
  created_at: string
}

export interface EvaluationRunReview {
  id: string
  domain: string
  source_type: string
  source_id: string
  algorithm_version: string
  result_status: string
  profile_eligibility: boolean
  profile_ineligibility_reasons: string[]
  adoption_status: string
  quality_gate: Record<string, unknown>
  input_provenance: Record<string, unknown>
  limitations: string[]
  dimension_results: ReviewDimension[]
  review_revisions: EvaluationReviewRevision[]
  created_at: string
}

export interface ReviewAudio {
  file_id: string
  url: string
}

export interface ReviewAttempt {
  id: string
  task: { id: string; title: string; instruction: string; target: string; type: string; session_date: string | null }
  attempt_no: number
  prompt_level: number
  status: string
  technical_validity: string
  measurement_eligibility: string
  audio_quality: string | null
  audio: ReviewAudio | null
  transcript: string | null
  analysis_status: string
  created_at: string
  duration_ms: number | null
}

export interface ReviewDialogue {
  id: string
  task: ReviewAttempt['task']
  status: string
  contract_version: string
  contract: Record<string, unknown>
  prompt_count: number
  turns: Array<{
    id: string
    index: number
    speaker: string
    speaker_label: string
    text: string
    audio: ReviewAudio | null
    asr_provider: string | null
    semantic_evidence: Record<string, unknown>
    dialogue_act: string
    created_at: string
  }>
}

export interface ReviewBundle {
  attention: ReviewQueueItem
  patient: { id: string; profile_id: string; name: string }
  goal: { id: string; category: string; description: string } | null
  active_plan: { id: string; version_number: number; stage_focus: string; status: string } | null
  source: { tasks: ReviewAttempt['task'][]; attempts: ReviewAttempt[]; dialogues: ReviewDialogue[] }
  audio_assets: ReviewAudio[]
  evaluation_runs: EvaluationRunReview[]
  metrics: Array<{ id: string; code: string; value: number | null; unit: string | null; status: string; quality: Record<string, unknown>; evidence_ids: string[]; measured_at: string }>
  evidence: Array<{ id: string; type: string; source_type: string; source_id: string; quality_status: string; provider: string | null; provider_version: string | null; payload: Record<string, unknown>; measured_at: string }>
  review_history: Array<{ id: string; run_id: string; action: string; reason: string | null; created_at: string | null; reviewer_user_id: string | null; automatic: Record<string, unknown>; revised: Record<string, unknown>; recomputed_run_id: string | null }>
  events: Array<{ id: string; event_type: string; from_status: string | null; to_status: string | null; note: string | null; related_refs: Record<string, unknown>; created_at: string }>
  quality: { audio_available: boolean; audio_missing: boolean; has_evaluation: boolean; source_refs_resolved: boolean }
  available_actions: string[]
}

export interface EvaluationReviewPayload {
  review_action: 'confirmed' | 'corrected' | 'unjudgeable'
  dimension_result_id?: string
  revised_value_snapshot?: Record<string, unknown>
  evidence_override?: Record<string, unknown>
  reason_code?: 'asr_mismatch' | 'audio_unavailable' | 'noise' | 'task_not_applicable' | 'not_observed' | 'insufficient_evidence' | 'other'
  reason?: string
  review_request_key: string
}

export interface StageReviewData {
  id: string
  status: string
  version: number
  patient: { user_id: string; name: string } | null
  goal: { id: string; category: string; description: string } | null
  active_plan: { id: string; version_number: number; stage_focus: string; status: string } | null
  patient_context: Record<string, unknown>
  primary_attention_item_id: string | null
  attention_item_ids: string[]
  review_window: { from?: string | null; to?: string | null }
  facts: { metrics?: unknown[]; trends?: Array<{ code: string; label: string; explanation: string }> }
  observations: Array<{ id: string; statement: string }>
  recommendations: Array<{ id: string; candidate_action: string }>
  formal_assessments: Array<{ id: string; instrument_name: string; instrument_version: string; assessed_at: string; review_status: string; measured_metrics: string[]; missing_items: unknown[] }>
  clinical_stage_support: Array<{ id: string; result_status: string; algorithm_version: string; created_at: string }>
  evidence_review_revisions: Array<{ id: string; evaluation_run_id: string; action: string; reason: string | null; automatic: Record<string, unknown>; revised: Record<string, unknown>; created_at: string }>
  therapist_notes: string | null
  ready_at: string | null
  finalized_at: string | null
  decision: { id: string; decision_type: string; reason: string; result: Record<string, unknown>; attention_resolution_policy: string; resulting_training_plan_version_id: string | null; decided_at: string } | null
}

export interface PlanEditorData {
  id: string
  patient_profile_id: string
  patient_user_id: string
  rehabilitation_goal_id: string
  rehabilitation_goal: { id: string; category: string; description: string } | null
  patient_name: string
  successor_stage_review_id?: string | null
  version_number: number
  status: string
  stage_focus: string
  strategy: Record<string, unknown>
  effective_from: string | null
  effective_to: string | null
  published_at: string | null
  supersedes_id: string | null
  source_decision_id: string | null
  exercise_rules: Array<{ id: string; task_template_id: string; exercise_type: 'repeat' | 'scenario'; sequence_role: 'warmup' | 'main' | 'consolidation' | 'challenge'; order_index: number; estimated_duration_seconds: number; title: string | null; target_repetitions: number; difficulty: string; max_information_units: number | null; prompt_policy: Record<string, unknown>; scene_scope: Record<string, unknown> }>
  active_plan: { id: string; version_number: number; stage_focus: string; status: string; exercise_rules: PlanEditorData['exercise_rules'] } | null
  abandon_reason: string | null
  abandoned_at: string | null
}

export const reviewWorkflowApi = {
  queue: (filters: { status?: string; type?: string; priority?: string; patient?: string; assigned_to?: string; cursor?: string | null; limit?: number } = {}) => {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) if (value) query.set(key, String(value))
    return request<ReviewQueueResponse>(http.get(`/v2/therapist/review-queue?${query.toString()}`))
  },
  bundle: (itemId: string) => request<ReviewBundle>(http.get(`/v2/therapist/attention-items/${itemId}/review-bundle`)),
  begin: (itemId: string) => request<ReviewQueueItem>(http.post(`/v2/therapist/attention-items/${itemId}/begin-review`)),
  release: (itemId: string) => request<ReviewQueueItem>(http.post(`/v2/therapist/attention-items/${itemId}/release`)),
  waitForInformation: (itemId: string, reason: string, note: string) => request<ReviewQueueItem>(http.post(`/v2/therapist/attention-items/${itemId}/wait-for-information`, { reason, note })),
  audioOpened: (itemId: string, fileId: string) => request<{ recorded: boolean }>(http.post(`/v2/therapist/attention-items/${itemId}/audio-opened`, { file_id: fileId })),
  submitEvaluationReview: (itemId: string, runId: string, payload: EvaluationReviewPayload) => request<{ run: EvaluationRunReview; revision_id: string | null }>(http.post(`/v2/therapist/attention-items/${itemId}/evaluation-runs/${runId}/reviews`, payload)),
  createStageReview: (itemId: string, payload: { additional_attention_item_ids?: string[]; review_from?: string | null; review_to?: string | null; therapist_notes?: string | null }) => request<StageReviewData & { reused?: boolean }>(http.post(`/v2/therapist/attention-items/${itemId}/stage-review`, payload)),
  stageReview: (id: string) => request<StageReviewData>(http.get(`/v2/therapist/stage-reviews/${id}`)),
  readyStageReview: (id: string) => request<StageReviewData>(http.post(`/v2/therapist/stage-reviews/${id}/ready`)),
  createDecision: (id: string, payload: { decision_type: string; reason: string; source_attention_item_ids?: string[]; attention_resolution_policy?: string; expected_review_version: number; request_key: string; payload?: Record<string, unknown> }) => request<{ id: string; resulting_training_plan_version_id: string | null; result: Record<string, unknown> }>(http.post(`/v2/therapist/stage-reviews/${id}/decisions`, payload)),
  plan: (id: string) => request<PlanEditorData>(http.get(`/v2/therapist/training-plans/${id}`)),
  planDiff: (id: string) => request<{ baseline_plan_id: string | null; baseline: Record<string, unknown> | null; draft: Record<string, unknown> }>(http.get(`/v2/therapist/training-plans/${id}/diff`)),
  updatePlan: (id: string, payload: { stage_focus: string; strategy: Record<string, unknown>; rehabilitation_goal_id: string; exercise_rules: PlanEditorData['exercise_rules'] extends Array<infer T> ? Array<Omit<T, 'id' | 'title'>> : never; expected_active_plan_id: string | null }) => request<PlanEditorData>(http.patch(`/v2/therapist/training-plans/${id}`, payload)),
  abandonPlan: (id: string, reason: string) => request<PlanEditorData>(http.post(`/v2/therapist/training-plans/${id}/abandon`, { reason })),
  publishPlan: (patientUserId: string, planId: string, expectedActivePlanId: string | null, requestKey: string) => request<PlanEditorData>(http.post(`/v2/therapist/patients/${patientUserId}/training-plans/${planId}/publish`, { expected_active_plan_id: expectedActivePlanId, request_key: requestKey })),
}

export function newRequestKey(): string {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
}
