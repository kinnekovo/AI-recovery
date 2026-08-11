import { http, request } from './http'
import type {
  AssessmentCompare,
  AssessmentCreatePayload,
  AssessmentReviewPayload,
  AssessmentReviewStatus,
  AssessmentSession,
  AssessmentType,
  TherapistPatient
} from '@/types/api'

export const therapistApi = {
  patients() {
    return request<TherapistPatient[]>(http.get('/therapist/patients'))
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
