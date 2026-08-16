import { http, request } from './http'
import type {
  AbilityProfile,
  AssessmentCompare,
  AssessmentCreatePayload,
  AssessmentReviewPayload,
  AssessmentReviewStatus,
  AssessmentSession,
  AssessmentType,
  Phase3DemoStatus,
  RecommendationNote,
  RecommendationNotePayload,
  RecommendationEffectSummary,
  StrategyFeedback,
  StrategyFeedbackPayload,
  TherapistTrainingRecord,
  TherapistTrainingTrends,
  TaskTemplate,
  TaskTemplatePayload,
  TrainingRecommendation,
  TrainingRecommendationReviewPayload,
  TherapistPatient
} from '@/types/api'

export const therapistApi = {
  patients() {
    return request<TherapistPatient[]>(http.get('/therapist/patients'))
  },
  taskTemplates(includeInactive = false) {
    return request<TaskTemplate[]>(
      http.get('/therapist/task-templates', {
        params: { include_inactive: includeInactive }
      })
    )
  },
  createTaskTemplate(payload: TaskTemplatePayload) {
    return request<TaskTemplate>(http.post('/therapist/task-templates', payload))
  },
  createAssessment(patientUserId: string, payload: AssessmentCreatePayload) {
    return request<AssessmentSession>(http.post(`/therapist/patients/${patientUserId}/assessments`, payload))
  },
  assessmentHistory(patientUserId: string, assessmentType?: AssessmentType, reviewStatus?: AssessmentReviewStatus) {
    return request<AssessmentSession[]>(
      http.get(`/therapist/patients/${patientUserId}/assessments`, {
        params: {
          ...(assessmentType ? { assessment_type: assessmentType } : {}),
          ...(reviewStatus ? { review_status: reviewStatus } : {})
        }
      })
    )
  },
  reviewAssessment(patientUserId: string, assessmentId: string, payload: AssessmentReviewPayload) {
    return request<AssessmentSession>(
      http.patch(`/therapist/patients/${patientUserId}/assessments/${assessmentId}/review`, payload)
    )
  },
  abilityProfile(patientUserId: string) {
    return request<AbilityProfile>(http.get(`/therapist/patients/${patientUserId}/ability-profile`))
  },
  trainingRecommendation(patientUserId: string) {
    return request<TrainingRecommendation>(http.get(`/therapist/patients/${patientUserId}/training-recommendation`))
  },
  trainingRecords(patientUserId: string) {
    return request<TherapistTrainingRecord[]>(http.get(`/therapist/patients/${patientUserId}/training-records`))
  },
  trainingTrends(patientUserId: string) {
    return request<TherapistTrainingTrends>(http.get(`/therapist/patients/${patientUserId}/training-trends`))
  },
  recommendationNote(patientUserId: string) {
    return request<RecommendationNote>(http.get(`/therapist/patients/${patientUserId}/recommendation-note`))
  },
  saveRecommendationNote(patientUserId: string, payload: RecommendationNotePayload) {
    return request<RecommendationNote>(http.post(`/therapist/patients/${patientUserId}/recommendation-note`, payload))
  },
  // Deprecated compatibility wrapper. The therapist UI should use recommendationNote
  // instead of making recommendation review a required approval step.
  reviewTrainingRecommendation(patientUserId: string, payload: TrainingRecommendationReviewPayload) {
    return request<TrainingRecommendation>(
      http.post(`/therapist/patients/${patientUserId}/training-recommendation/review`, payload)
    )
  },
  recommendationEffects(patientUserId: string) {
    return request<RecommendationEffectSummary>(
      http.get(`/therapist/patients/${patientUserId}/training-recommendation/effects`)
    )
  },
  // Deprecated compatibility wrapper. Trend attribution now comes from recommendationEffects.
  createStrategyFeedback(patientUserId: string, payload: StrategyFeedbackPayload) {
    return request<StrategyFeedback>(
      http.post(`/therapist/patients/${patientUserId}/training-recommendation/strategy-feedback`, payload)
    )
  },
  phase3DemoStatus() {
    return request<Phase3DemoStatus>(http.get('/therapist/phase3/demo-status'))
  },
  assessmentCompare(patientUserId: string, baselineId?: string, currentId?: string) {
    return request<AssessmentCompare>(
      http.get(`/therapist/patients/${patientUserId}/assessments/compare`, {
        params: {
          ...(baselineId ? { baseline_id: baselineId } : {}),
          ...(currentId ? { current_id: currentId } : {})
        }
      })
    )
  }
}
