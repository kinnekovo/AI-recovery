export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

export interface User {
  id: string
  username: string
  role: 'patient'
  status: string
  created_at: string
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
  created_at: string
  session_tasks: SessionTask[]
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

export interface ScoreResult {
  attempt_id: string
  overall_score: number
  dimensions: {
    content: number
    clarity: number
    fluency: number
    loudness: number
    prompt_dependence: number
  }
  feedback: {
    strength: string
    improve: string
  }
  transcript?: string | null
}

export interface LatestReport {
  training_count: number
  average_score: number
  suggestion: string
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
