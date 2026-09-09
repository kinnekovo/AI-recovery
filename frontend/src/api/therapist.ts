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
  TherapistTrainingRecord,
  TherapistTrainingTrends,
  TherapistTrialQuality,
  TaskTemplate,
  TaskTemplatePayload,
  TrainingRecommendation,
  TherapistPatient,
  PronunciationAnalysis,
  PronunciationRevisionPayload,
  IntelligibilityReviewPayload,
  TherapistInterRaterAgreement,
  ScenarioExpressionReview,
  ScenarioExpressionReviewPayload,
  TherapistScenarioDialogue,
  ScenarioDialogueEvaluation,
  TherapistScenarioDialogueListItem
} from '@/types/api'

export const therapistApi = {
  patients() {
    return request<TherapistPatient[]>(http.get('/therapist/patients'))
  },
  trialQuality() {
    return request<TherapistTrialQuality>(http.get('/therapist/trial-quality'))
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
  scenarioReview(patientUserId: string, attemptId: string) {
    return request<ScenarioExpressionReview>(http.get(`/therapist/patients/${patientUserId}/attempts/${attemptId}/scenario-review`))
  },
  scenarioDialogue(dialogueId: string) {
    return request<TherapistScenarioDialogue>(http.get(`/therapist/scenario-dialogues/${dialogueId}`))
  },
  scenarioDialogues(patientUserId: string) {
    return request<TherapistScenarioDialogueListItem[]>(http.get(`/therapist/patients/${patientUserId}/scenario-dialogues`))
  },
  saveScenarioDialogueReview(dialogueId: string, payload: { evidence_overrides: Record<string, unknown>; review_notes?: string | null; review_status: string }) {
    return request<ScenarioDialogueEvaluation>(http.patch(`/therapist/scenario-dialogues/${dialogueId}/review`, payload))
  },
  saveScenarioReview(patientUserId: string, attemptId: string, payload: ScenarioExpressionReviewPayload) {
    return request<ScenarioExpressionReview>(http.patch(`/therapist/patients/${patientUserId}/attempts/${attemptId}/scenario-review`, payload))
  },
  pronunciationInterRaterAgreement(patientUserId: string) {
    return request<TherapistInterRaterAgreement>(
      http.get(`/therapist/patients/${patientUserId}/pronunciation/inter-rater-agreement`)
    )
  },
  pronunciation(analysisId: string) {
    return request<PronunciationAnalysis>(http.get(`/therapist/pronunciation/${analysisId}`))
  },
  revisePronunciation(analysisId: string, payload: PronunciationRevisionPayload) {
    return request<PronunciationAnalysis>(http.post(`/therapist/pronunciation/${analysisId}/revisions`, payload))
  },
  addIntelligibilityReview(analysisId: string, payload: IntelligibilityReviewPayload) {
    return request<PronunciationAnalysis>(http.post(`/therapist/pronunciation/${analysisId}/intelligibility-reviews`, payload))
  },
  completePronunciationReview(analysisId: string) {
    return request<PronunciationAnalysis>(http.post(`/therapist/pronunciation/${analysisId}/complete-review`))
  },
  trainingTrends(patientUserId: string) {
    return request<TherapistTrainingTrends>(http.get(`/therapist/patients/${patientUserId}/training-trends`))
  },
  stageReportExport(patientUserId: string) {
    return http.get<Blob>(`/therapist/patients/${patientUserId}/stage-report/export`, {
      responseType: 'blob'
    })
  },
  recommendationNote(patientUserId: string) {
    return request<RecommendationNote>(http.get(`/therapist/patients/${patientUserId}/recommendation-note`))
  },
  saveRecommendationNote(patientUserId: string, payload: RecommendationNotePayload) {
    return request<RecommendationNote>(http.post(`/therapist/patients/${patientUserId}/recommendation-note`, payload))
  },
  recommendationEffects(patientUserId: string) {
    return request<RecommendationEffectSummary>(
      http.get(`/therapist/patients/${patientUserId}/training-recommendation/effects`)
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
