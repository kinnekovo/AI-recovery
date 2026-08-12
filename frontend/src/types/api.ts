export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

export interface User {
  id: string
  username: string
  role: UserRole
  status: string
  created_at: string
}

export type UserRole = 'patient' | 'family' | 'therapist' | 'admin'

export interface PatientProfile {
  id: string
  user_id: string
  current_agent_id: string | null
  onboarding_status: string
  assessment_status: string
  training_status: string
}

export interface Agent {
  id: string
  name: string
  relationship: string
  personality_style: string
  avatar_file_id: string | null
  voice_sample_file_id: string | null
  welcome_audio_file_id: string | null
  voice_external_id: string | null
  generation_status: string
  image_consent_confirmed: boolean
  voice_consent_confirmed: boolean
  created_at: string
}

export interface TaskTemplate {
  id: string
  task_type: 'repeat' | 'scenario'
  title: string
  instruction: string
  target_text: string
  content_level: string
  autonomy_level: string
  scene_prompt?: string | null
}

export interface SessionTask {
  id: string
  order_index: number
  prompt_level: number
  status: string
  task_template: TaskTemplate
}

export interface TrainingSession {
  id: string
  training_type: 'repeat' | 'scenario'
  status: string
  agent_id: string | null
  recommendation_review_id: string | null
  recommendation_source: string | null
  recommendation_snapshot: Record<string, unknown> | null
  recommendation_matched: boolean
  created_at: string
  session_tasks: SessionTask[]
}

export interface TrainingRecommendation {
  id: string | null
  recommended_type: 'repeat' | 'scenario'
  headline: string
  reason: string
  focus_points: string[]
  suggested_minutes: number
  content_level: string
  autonomy_level: string
  confidence: number
  profile_summary: string
  source: 'system' | 'therapist' | string
  review_status: 'pending_review' | 'confirmed' | 'adjusted' | string
  therapist_notes: string | null
  updated_at: string | null
  task_template: TaskTemplate | null
}

export interface TrainingRecommendationReviewPayload {
  recommended_type: 'repeat' | 'scenario'
  headline: string
  reason: string
  focus_points: string[]
  suggested_minutes: number
  therapist_notes?: string | null
}

export interface TrainingSessionCreatePayload {
  type: 'repeat' | 'scenario'
  recommendation_id?: string | null
  recommendation_source?: string | null
  recommendation_headline?: string | null
}

export interface RecommendationEffect {
  session_id: string
  created_at: string
  training_type: 'repeat' | 'scenario'
  recommendation_source: string | null
  recommendation_headline: string | null
  recommendation_matched: boolean
  status: string
  metrics: Partial<ProcessMetrics>
  summary: string
}

export interface RecommendationEffectSummary {
  total_recommended_sessions: number
  completed_recommended_sessions: number
  matched_sessions: number
  latest: RecommendationEffect[]
}

export interface Attempt {
  id: string
  session_task_id: string
  attempt_no: number
  audio_file_id: string | null
  prompt_level: number
  duration_ms: number | null
  skipped: boolean
  requested_help: boolean
  audio_quality: string | null
  analysis_status: string
  created_at: string
}

export interface ProcessMetrics {
  script_accuracy: number
  error_count: number
  speech_rate: number
  loudness: number
}

export interface TrainingFeedbackItem {
  metric: 'script_accuracy' | 'error_count' | 'speech_rate' | 'loudness' | string
  current_performance: string
  suggestion: string
}

export interface TrainingFeedbackResult {
  attempt_id: string
  process_metrics: ProcessMetrics
  feedback: TrainingFeedbackItem[]
  transcript?: string | null
}

export interface LatestReport {
  training_count: number
  process_monitoring_summary: ProcessMonitoringSummary
  effect_comparison: ReportEffectComparison
  suggestion: string
}

export interface ProcessMonitoringSummary {
  avg_script_accuracy: number | null
  avg_error_count: number | null
  avg_speech_rate: number | null
  avg_loudness: number | null
}

export interface ReportMetricComparison {
  baseline: number | null
  current: number | null
  change: number | null
}

export interface ReportEffectComparison {
  has_comparison: boolean
  wab: Record<string, ReportMetricComparison>
  cadl: ReportMetricComparison | null
  acceptance: ReportMetricComparison | null
}

export type EvaluationMetricCategory = 'process' | 'long_term_effect'
export type EvaluationSource = 'mock_ai' | 'human' | 'clinician'

export interface EvaluationMetric {
  id: string
  name: string
  category: EvaluationMetricCategory
  description: string
  unit: string | null
  normal_range: Record<string, unknown>
  created_at: string
}

export interface AttemptEvaluation {
  id: string
  attempt_id: string
  metric_id: string
  metric_name: string
  metric_category: EvaluationMetricCategory
  value: number
  evaluation_source: EvaluationSource
  created_at: string
}

export interface AttemptEvaluationInput {
  metric_id?: string
  metric_name?: string
  value: number
  evaluation_source?: EvaluationSource
}

export interface AttemptEvaluationBatch {
  attempt_id: string
  items: AttemptEvaluation[]
}

export interface ProcessTrendPoint {
  attempt_id: string
  created_at: string
  metrics: ProcessMetrics
}

export interface ProcessTrend {
  items: ProcessTrendPoint[]
}

export type AssessmentType = 'baseline' | 'during' | 'after_30_days' | 'post_training'
export type AssessmentReviewStatus = 'auto_generated' | 'pending_review' | 'confirmed' | 'adjusted'

export interface AssessmentMetrics {
  wab_information?: number | null
  wab_fluency?: number | null
  wab_grammar?: number | null
  wab_word_order?: number | null
  wab_comprehensibility?: number | null
  wab_repetition_comprehensibility?: number | null
  cadl_score?: number | null
  acceptance_score?: number | null
}

export interface AssessmentCreatePayload {
  assessment_type: AssessmentType
  evaluation_source?: Exclude<EvaluationSource, 'mock_ai'>
  assessed_at?: string | null
  metrics: AssessmentMetrics
  notes?: string | null
}

export interface AssessmentSession {
  id: string
  patient_profile_id: string
  source_attempt_id: string | null
  assessment_type: AssessmentType
  evaluation_source: EvaluationSource
  review_status: AssessmentReviewStatus
  reviewed_by_user_id: string | null
  reviewed_at: string | null
  assessed_at: string
  metrics: Record<string, number>
  notes: string | null
  therapist_notes: string | null
  created_at: string
}

export interface AssessmentReviewPayload {
  review_status: Extract<AssessmentReviewStatus, 'confirmed' | 'adjusted'>
  metrics?: Record<string, number> | null
  notes?: string | null
  therapist_notes?: string | null
}

export interface MetricComparison {
  baseline: number | null
  current: number | null
  change: number | null
}

export interface AssessmentCompare {
  baseline_assessment: AssessmentSession | null
  current_assessment: AssessmentSession | null
  metrics: Record<string, MetricComparison>
}

export interface TherapistPatient {
  user_id: string
  patient_profile_id: string
  username: string
  assessment_status: string
  training_status: string
  pending_review_count: number
  latest_assessment_at: string | null
  created_at: string
}

export interface AbilityProfile {
  id: string
  patient_profile_id: string
  current_content_level: string
  current_autonomy_level: string
  avg_script_accuracy_recent: number | null
  avg_error_count_recent: number | null
  avg_speech_rate_recent: number | null
  avg_loudness_recent: number | null
  assessment_summary: string
  recommendation: string
  confidence: number
  evidence: {
    recent_attempt_count?: number
    reviewed_assessment_count?: number
    latest_review_status?: string | null
    latest_therapist_notes?: string | null
    [key: string]: unknown
  }
  updated_at: string
}
