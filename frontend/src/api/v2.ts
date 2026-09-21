import { http, request } from './http'

export interface GoalV2 {
  id: string
  category: string
  description: string
  status: string
  effective_from: string
  effective_to: string | null
}

export interface PlanRuleV2 {
  id: string
  task_template_id: string
  exercise_type: 'repeat' | 'scenario'
  order_index: number
  title: string | null
  difficulty: string
  max_information_units: number | null
  prompt_policy: Record<string, unknown>
}

export interface TrainingPlanV2 {
  id: string
  patient_profile_id: string
  rehabilitation_goal_id: string
  version_number: number
  status: string
  stage_focus: string
  strategy: { duration?: number; frequency?: string; forms?: string[]; difficulty?: string; prompt_policy?: Record<string, unknown> }
  effective_from: string | null
  effective_to: string | null
  published_at: string | null
  supersedes_id: string | null
  exercise_rules: PlanRuleV2[]
}

export interface AttemptV2 {
  id: string
  attempt_no: number
  prompt_level: number
  terminal_state: string
  technical_validity: string
  measurement_eligibility: string
  analysis_status: string
  audio_file_id: string | null
  requested_help: boolean
  skipped: boolean
}

export interface ExerciseV2 {
  id: string
  order_index: number
  status: string
  exercise_type: 'repeat' | 'scenario'
  title: string
  instruction: string
  target: string
  difficulty: string | null
  max_information_units: number | null
  prompt_level: number
  prompt_policy: Record<string, unknown>
  scenario_dialogue_id: string | null
  attempts: AttemptV2[]
}

export interface TrainingSessionV2 {
  id: string
  patient_profile_id: string
  plan_version_id: string
  session_kind: 'formal' | 'extra_practice'
  status: 'planned' | 'in_progress' | 'paused' | 'completed' | 'aborted'
  local_session_date: string
  started_at: string | null
  paused_at: string | null
  completed_at: string | null
  summary_status: string
  technical_status: string
  exercises: ExerciseV2[]
  current_exercise: ExerciseV2 | null
  resume_position: number
}

export interface PatientHomeV2 {
  state: 'onboarding_required' | 'waiting_for_plan' | 'ready_to_train' | 'in_progress' | 'paused' | 'completed' | 'stage_review_pending' | 'plan_updated' | 'temporarily_unavailable'
  greeting: string
  active_rehabilitation_goal: GoalV2 | null
  active_training_plan: TrainingPlanV2 | null
  stage_focus: string | null
  today_session: TrainingSessionV2 | null
  today_training_structure: PlanRuleV2[]
  estimated_duration: number | null
  primary_action: { label: string; action: string } | null
  recent_comparable_changes: TrendV2[]
  plan_update_announcement: string | null
}

export interface TrendV2 {
  code: string
  label: string
  comparability: { status: string; included_measurement_ids: string[]; excluded: unknown[] }
  trend: { status: string; sample_count: number; delta?: number; slope?: number; mean?: number; median?: number }
  explanation: string
}

export interface ProgressV2 {
  recent_summary: string
  comparable_trends: TrendV2[]
  milestones: Array<{ id: string; code: string; title: string; description: string; achieved_at: string; source_status: 'real' | 'mock' }>
  training_adherence: { formal_sessions: number; completed_sessions: number; status: string }
  insufficient_data: boolean
}

export interface AttentionItemV2 {
  id: string
  patient_user_id: string
  patient: string
  type: string
  trigger_code: string
  trigger_facts: Record<string, unknown>
  source_refs: Array<Record<string, unknown>>
  evidence_ids: string[]
  priority: string
  summary: string
  status: string
  created_at: string
  resolved_at: string | null
}

export interface WorkbenchV2 {
  summary: { open: number; acknowledged: number }
  attention_items: AttentionItemV2[]
  generated_at: string
}

export interface MetricV2 {
  id?: string
  code: string
  label: string
  value: number | null
  status: string
  unit: string | null
  display_source?: string
  measured_at?: string
  provider?: string | null
  algorithm?: string | null
  instrument?: string | null
  version?: string | null
  quality?: Record<string, unknown>
  evidence_ids?: string[]
  message?: string
  source?: { type: string; id: string }
}

export interface ExerciseProfessionalDetailV2 {
  session_id: string
  exercise: ExerciseV2
  exercise_type: 'repeat' | 'scenario'
  professional_metrics: MetricV2[]
  metrics: MetricV2[]
  evidence: Array<Record<string, unknown>>
  scenario_dialogue: Record<string, unknown> | null
}

export interface SessionDetailV2 {
  overview: TrainingSessionV2
  evidence: Array<Record<string, unknown>>
  metrics: MetricV2[]
  professional_metrics: MetricV2[]
  comparability: Array<Record<string, unknown>>
  observations: Array<Record<string, unknown>>
  recommendations: Array<Record<string, unknown>>
  therapist_actions: string[]
}

export const isProductV2Enabled = (value: string | undefined) => value !== 'false'
export const productV2Enabled = isProductV2Enabled(import.meta.env.VITE_PRODUCT_V2_ENABLED)

export const v2Api = {
  patientHome: () => request<PatientHomeV2>(http.get('/v2/patient/home')),
  progress: () => request<ProgressV2>(http.get('/v2/patient/progress')),
  patientSettings: () => request<{ timezone: string }>(http.get('/v2/patient/settings')),
  updatePatientSettings: (timezone: string) => request<{ timezone: string }>(http.patch('/v2/patient/settings', { timezone })),
  startOrResume: (session_kind: 'formal' | 'extra_practice' = 'formal') => request<TrainingSessionV2>(http.post('/v2/patient/training-sessions/start-or-resume', { session_kind })),
  session: (id: string) => request<TrainingSessionV2>(http.get(`/v2/patient/training-sessions/${id}`)),
  sessionCommand: (id: string, command: string, reason?: string) => request<TrainingSessionV2>(http.post(`/v2/patient/training-sessions/${id}/${command}`, { reason: reason || null })),
  exerciseCommand: (sessionId: string, taskId: string, command: string) => request<TrainingSessionV2>(http.post(`/v2/patient/training-sessions/${sessionId}/exercises/${taskId}/${command}`)),
  summary: (id: string) => request<Record<string, unknown>>(http.get(`/v2/patient/training-sessions/${id}/summary`)),
  createAttempt: (session_task_id: string, prompt_level: number) => request<{ id: string }>(http.post('/v2/patient/attempts', { session_task_id, prompt_level })),
  uploadAttempt: (attemptId: string, blob: Blob) => {
    const form = new FormData()
    form.append('audio_file', blob, 'training.webm')
    return request<Record<string, unknown>>(http.post(`/v2/patient/attempts/${attemptId}/audio`, form))
  },
  analyzeAttempt: (attemptId: string) => request<{ attempt: AttemptV2; feedback: Record<string, unknown> }>(http.post(`/v2/patient/attempts/${attemptId}/analyze`)),
  workbench: () => request<WorkbenchV2>(http.get('/v2/therapist/workbench')),
  workspace: (patientId: string) => request<Record<string, any>>(http.get(`/v2/therapist/patients/${patientId}/workspace`)),
  therapistSession: (sessionId: string) => request<SessionDetailV2>(http.get(`/v2/therapist/training-sessions/${sessionId}`)),
  therapistExercise: (sessionId: string, taskId: string) => request<ExerciseProfessionalDetailV2>(http.get(`/v2/therapist/training-sessions/${sessionId}/exercises/${taskId}`)),
  plans: (patientId: string) => request<TrainingPlanV2[]>(http.get(`/v2/therapist/patients/${patientId}/training-plans`)),
  createGoal: (patientId: string, payload: Record<string, unknown>) => request<GoalV2>(http.post(`/v2/therapist/patients/${patientId}/rehabilitation-goals`, payload)),
  createPlan: (patientId: string, payload: Record<string, unknown>) => request<TrainingPlanV2>(http.post(`/v2/therapist/patients/${patientId}/training-plans`, payload)),
  publishPlan: (patientId: string, planId: string) => request<TrainingPlanV2>(http.post(`/v2/therapist/patients/${patientId}/training-plans/${planId}/publish`)),
  acknowledgeAttention: (id: string) => request<AttentionItemV2>(http.post(`/v2/therapist/attention-items/${id}/acknowledge`)),
  resolveAttention: (id: string, resolution_note: string, status = 'resolved') => request<AttentionItemV2>(http.post(`/v2/therapist/attention-items/${id}/resolve`, { resolution_note, status })),
  createStageReview: (patientId: string, payload: Record<string, unknown> = {}) => request<Record<string, any>>(http.post(`/v2/therapist/patients/${patientId}/stage-reviews`, payload)),
  stageReview: (id: string) => request<Record<string, any>>(http.get(`/v2/therapist/stage-reviews/${id}`)),
  createDecision: (reviewId: string, payload: Record<string, unknown>) => request<Record<string, any>>(http.post(`/v2/therapist/stage-reviews/${reviewId}/decisions`, payload)),
  createFormalAssessment: (patientId: string, payload: Record<string, unknown>) => request<Record<string, unknown>>(http.post(`/v2/therapist/patients/${patientId}/formal-assessments`, payload)),
  providerMatrix: () => request<Array<Record<string, unknown>>>(http.get('/v2/provider-matrix'))
}
