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

export interface HealthStatus {
  status: string
  database: {
    status: string
  }
  storage: {
    status: string
    root: string
    exists: boolean
    is_dir: boolean
  }
  providers: Record<string, ProviderHealthStatus>
}

export interface ProviderHealthStatus {
  name: string
  provider: string
  mode: string
  status: string
  ready: boolean
  missing_env: string[]
  message: string
}

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
  avatar_url: string | null
  avatar_animation_config: Record<string, unknown> | null
  voice_sample_file_id: string | null
  welcome_audio_file_id: string | null
  voice_external_id: string | null
  voice_clone_task_id: string | null
  voice_training_text: string | null
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
  scoring_config?: Record<string, unknown>
  tags: string[]
  recommendation_weight: number
  is_active: boolean
}

export interface TaskTemplatePayload {
  task_type: 'repeat' | 'scenario'
  title: string
  instruction: string
  target_text: string
  content_level: string
  autonomy_level: string
  scene_prompt?: string | null
  scoring_config?: Record<string, unknown>
  tags: string[]
  recommendation_weight: number
  is_active: boolean
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
  task_sequence: TaskTemplate[]
  policy_version: string
  adaptation_note: string | null
  reminder: string | null
}

export interface TrainingRecommendationReviewPayload {
  recommended_type: 'repeat' | 'scenario'
  headline: string
  reason: string
  focus_points: string[]
  suggested_minutes: number
  therapist_notes?: string | null
}

export interface TherapistTrainingRecord {
  attempt_id: string
  session_id: string
  created_at: string
  training_type: 'repeat' | 'scenario'
  task_title: string
  target_text: string
  analysis_status: string
  pronunciation_analysis_id: string | null
  pronunciation_status: string | null
  pronunciation_shadow_score: number | null
  overall_score: number | null
  content_score: number | null
  clarity_score: number | null
  fluency_score: number | null
  loudness_score: number | null
  process_metrics: Partial<ProcessMetrics>
  process_details: ProcessDetails | null
  audio_url: string | null
  asr_text: string | null
  feedback_summary: string
  recommendation_source: string | null
  recommendation_matched: boolean
  scenario_review_status: 'pending_review' | 'confirmed' | 'adjusted' | null
  scenario_review_notes: string | null
}

export interface ScenarioDialogueTurn {
  turn_index: number
  speaker: 'agent' | 'patient'
  dialogue_act: string
  text: string
  created_at: string
}

export interface ScenarioDialogue {
  id: string
  status: 'active' | 'completed' | 'aborted'
  current_state: string
  patient_turn_count: number
  prompt_count: number
  maximum_prompt_level: number
  communication_goal: string
  turns: ScenarioDialogueTurn[]
}

export interface ScenarioDialogueEvaluation {
  goal_status: 'achieved' | 'partly_achieved' | 'not_achieved'
  goal_score: number
  information_score: number
  response_score: number
  relevance_score: number
  independence_score: number
  repair_score: number | null
  overall_score: number | null
  confidence: number
  review_status: string
  evidence_snapshot: { collected_information_unit_ids?: string[]; required_information_unit_ids?: string[]; fallback_used?: boolean }
  scoring_version: string
}

export interface TherapistScenarioDialogueTurn extends ScenarioDialogueTurn {
  audio_file_id: string | null
}

export interface TherapistScenarioDialogue {
  id: string
  status: string
  current_state: string
  patient_turn_count: number
  prompt_count: number
  maximum_prompt_level: number
  communication_goal: string
  turns: TherapistScenarioDialogueTurn[]
}

export interface TherapistScenarioDialogueListItem {
  id: string
  created_at: string
  status: string
  current_state: string
  communication_goal: string
  patient_turn_count: number
  review_status: string | null
}

export interface ScenarioExpressionReview {
  attempt_id: string
  review_status: 'pending_review' | 'confirmed' | 'adjusted'
  goal_status: 'achieved' | 'partly_achieved' | 'not_achieved' | null
  information_unit_overrides: Record<string, boolean>
  notes: string | null
  reviewed_by_user_id: string | null
  reviewed_at: string | null
}

export interface ScenarioExpressionReviewPayload {
  review_status: 'confirmed' | 'adjusted'
  goal_status?: 'achieved' | 'partly_achieved' | 'not_achieved' | null
  information_unit_overrides?: Record<string, boolean>
  notes?: string | null
}

export interface TherapistTrendBucket {
  key: 'latest' | 'days_3' | 'days_7' | 'days_30' | string
  label: string
  attempt_count: number
  avg_overall_score: number | null
  avg_script_accuracy: number | null
  avg_error_count: number | null
  avg_speech_rate: number | null
  avg_loudness: number | null
  summary: string
}

export interface TherapistTrainingTrends {
  buckets: TherapistTrendBucket[]
  overall_summary: string
}

export interface TherapistInterRaterAgreement {
  patient_user_id: string
  listener_review_count: number
  double_labeled_attempt_count: number
  comparison_count: number
  mean_absolute_percent_difference: number | null
  within_ten_percent_rate: number | null
  mean_transcript_similarity: number | null
  summary: string
}

export interface PronunciationSegment {
  id: string
  level: 'word' | 'phoneme' | string
  ordinal: number
  reference_text: string | null
  recognized_text: string | null
  start_ms: number | null
  end_ms: number | null
  accuracy: number | null
  fluency: number | null
  match_type: 'matched' | 'addition' | 'omission' | 'substitution' | 'out_of_vocabulary' | 'unavailable' | string
  reference_tone: number | null
  recognized_tone: number | null
  tone_correct: boolean | null
}

export interface PronunciationRevision {
  id: string
  analysis_id: string
  segment_id: string | null
  metric_name: string
  original_value: Record<string, unknown>
  revised_value: Record<string, unknown>
  judgment: 'confirmed' | 'corrected' | 'unjudgeable' | string
  error_category: string | null
  reason: string | null
  reviewed_by_user_id: string
  created_at: string
}

export interface IntelligibilityReview {
  id: string
  analysis_id: string
  listener_role: string
  listener_transcript: string
  understood_percent: number
  playback_count: number
  listening_environment: string | null
  notes: string | null
  recorded_by_user_id: string
  created_at: string
}

export interface IntelligibilityReviewPayload {
  listener_role: string
  listener_transcript: string
  understood_percent: number
  playback_count: number
  listening_environment?: string | null
  notes?: string | null
}

export interface PronunciationAnalysis {
  id: string
  attempt_id: string
  provider: string
  provider_version: string
  evaluation_mode: string
  status: 'completed' | 'failed' | 'unavailable' | string
  overall_accuracy: number | null
  fluency: number | null
  completion: number | null
  suggested_score: number | null
  intelligibility_proxy: number | null
  confidence: number | null
  coverage: number
  prosody_metrics: Record<string, unknown>
  algorithm_version: string
  error_code: string | null
  error_message: string | null
  review_status: string
  reviewed_by_user_id: string | null
  segments: PronunciationSegment[]
  revisions: PronunciationRevision[]
  intelligibility_reviews: IntelligibilityReview[]
  created_at: string
}

export interface PronunciationRevisionPayload {
  segment_id?: string | null
  metric_name: string
  revised_value: Record<string, unknown>
  judgment: 'confirmed' | 'corrected' | 'unjudgeable'
  error_category?: string | null
  reason?: string | null
}

export interface TherapistTrialQuality {
  patient_count: number
  training_session_count: number
  completed_session_count: number
  completion_rate: number
  attempt_count: number
  missing_audio_count: number
  missing_audio_rate: number
  failed_analysis_count: number
  low_quality_attempt_count: number
  low_quality_rate: number
  provider_failure_count: number
}

export interface RecommendationNotePayload {
  note: string | null
}

export interface RecommendationNote {
  note: string | null
  updated_at: string | null
}

export interface TrainingSessionCreatePayload {
  type: 'repeat' | 'scenario'
  scenario_mode?: 'training' | 'generalization_probe'
  recommendation_id?: string | null
  recommendation_source?: string | null
  recommendation_headline?: string | null
  recommendation_task_ids?: string[] | null
}

export interface AvatarSpeechPayload {
  scene: 'training_intro' | 'session_intro' | 'task_demo' | 'next_task' | 'result_encouragement' | 'error_recovery' | string
  session_id?: string | null
  session_task_id?: string | null
  text: string
}

export interface AvatarSpeech {
  text: string
  audio_file_id: string | null
  audio_url: string | null
  provider: string
  fallback: boolean
  cached: boolean
  video_task: AvatarVideoTaskBrief | null
}

export interface AvatarVideoTaskBrief {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
}

export interface AvatarVideoTask {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  video_url: string | null
  error_message: string | null
  generation_ms: number | null
  created_at: string
}

export interface TodayTraining {
  plan_id: string
  title: string
  status: string
  items_count: number
  recommended_completed: boolean
  completed_recommended_sessions: number
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
  trend_status: 'observing' | 'effective' | 'needs_adjustment' | 'mixed' | string
  trend_summary: string
  strategy_hint: string
  evidence_points: string[]
  attribution_points: string[]
  reminder_level: 'info' | 'success' | 'warning' | string
  patient_reminder: string | null
  family_reminder: string | null
  therapist_reminder: string | null
  latest: RecommendationEffect[]
}

export interface StrategyFeedbackPayload {
  judgment: 'agree' | 'disagree' | 'observe'
  reason?: string | null
  next_strategy?: string | null
}

export interface StrategyFeedback {
  id: string
  patient_profile_id: string
  therapist_user_id: string
  trend_status: string
  judgment: string
  reason: string | null
  next_strategy: string | null
  created_at: string
}

export interface FamilyObservation {
  patient_username: string
  training_count: number
  completed_recommended_sessions: number
  last_training_at: string | null
  adherence_summary: string
  recommendation_headline: string
  recommendation_source: string
  trend_summary: string
  strategy_hint: string
  therapist_note: string | null
  reminder_level: 'info' | 'success' | 'warning' | string
  family_reminder: string | null
  current_level_label: string
  progress_label: string
  progress_percent: number
  level_items: FamilyLevelItem[]
  trend_items: FamilyTrendItem[]
  recent_records: FamilyTrainingRecord[]
  bound_patients: FamilyBoundPatient[]
  selected_patient_user_id: string | null
}

export interface FamilyBoundPatient {
  binding_id: string
  patient_user_id: string
  patient_profile_id: string
  patient_username: string
  relationship_label: string
  status: string
  created_at: string
}

export interface FamilyLevelItem {
  key: string
  label: string
  icon: string
  value: string
  level: number
  tone: 'good' | 'steady' | 'watch' | 'muted' | string
  hint: string
}

export interface FamilyTrendItem {
  label: string
  value: number
  summary: string
  created_at: string
}

export interface FamilyTrainingRecord {
  attempt_id: string
  created_at: string
  training_type: 'repeat' | 'scenario'
  task_title: string
  target_text: string
  audio_url: string | null
  asr_text: string | null
  summary: string
  metrics: Partial<ProcessMetrics>
}

export interface Phase3DemoStatus {
  has_patient: boolean
  has_recommendation: boolean
  has_therapist_review: boolean
  has_recommended_training: boolean
  has_effect_trend: boolean
  has_strategy_feedback: boolean
  next_step: string
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
  analysis_error_code: string | null
  analysis_error_message: string | null
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
  audio_url?: string | null
  process_details?: ProcessDetails | null
}

export interface ProcessDetails {
  correct_script_word_rate?: number
  correct_script_word_count?: number
  total_script_word_count?: number
  valid_word_count?: number
  speaking_duration_seconds?: number
  error_events?: Record<string, number>
  script_mismatch_events?: {
    substitution?: number
    addition?: number
    omission?: number
  }
  reference_ranges?: Record<string, string>
  input_sources?: Record<string, string>
  limitations?: string[]
  task_type?: 'repeat' | 'scenario'
  independence_score?: number
  scenario_evaluation?: ScenarioEvaluation | null
  [key: string]: unknown
}

export interface ScenarioInformationUnit {
  id: string
  label: string
  required: boolean
  matched: boolean
  matches: string[]
}

export interface ScenarioEvaluation {
  version: string
  communication_goal: string
  goal_status: 'achieved' | 'partly_achieved' | 'not_achieved' | string
  goal_score: number
  information_unit_score: number
  required_information_units: ScenarioInformationUnit[]
  optional_information_units: ScenarioInformationUnit[]
  matched_required_count: number
  required_count: number
  next_information_units: string[]
  repair_ability?: { status: string; reason: string }
  limitations?: string[]
}

export interface LatestReport {
  training_count: number
  process_monitoring_summary: ProcessMonitoringSummary
  scenario_communication_summary: ScenarioCommunicationSummary
  effect_comparison: ReportEffectComparison
  suggestion: string
}

export interface ProcessMonitoringSummary {
  avg_script_accuracy: number | null
  avg_error_count: number | null
  avg_speech_rate: number | null
  avg_loudness: number | null
}

export interface ScenarioCommunicationSummary {
  attempt_count: number
  recent_valid_count: number
  independent_goal_achievement_rate: number | null
  median_information_unit_score: number | null
  median_independence_score: number | null
  generalization_probe_count: number
  generalization_probe_distinct_date_count: number
  generalization_independent_goal_achievement_rate: number | null
  generalization_summary: string
  therapist_reviewed_count: number
  therapist_adjusted_count: number
  summary: string
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
export type EvaluationSource = 'mock_ai' | 'system_rule' | 'provider_ai' | 'human' | 'clinician'

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
  audio_url: string | null
  asr_text: string | null
  target_text: string | null
  process_details: ProcessDetails | null
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
  evaluation_source?: Exclude<EvaluationSource, 'mock_ai' | 'system_rule' | 'provider_ai'>
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
  source_audio_url: string | null
  source_asr_text: string | null
  source_target_text: string | null
  source_process_details: ProcessDetails | null
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
