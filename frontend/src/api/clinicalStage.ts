import { http, request } from './http'
import type { ClinicalStageDetail, ComparabilityResult, JsonObject } from '@/types/professional'
import type { AssessmentSession } from '@/types/api'

export const clinicalStageApi = {
  detail: (patientId: string, assessmentId: string) => request<ClinicalStageDetail>(http.get(`/therapist/patients/${patientId}/assessments/${assessmentId}/clinical-stage`)),
  preview: (patientId: string, assessmentId: string) => request<JsonObject>(http.get(`/therapist/patients/${patientId}/assessments/${assessmentId}/clinical-stage/preview`)),
  updateSource: (patientId: string, assessmentId: string, payload: JsonObject) => request<AssessmentSession>(http.patch(`/therapist/patients/${patientId}/assessments/${assessmentId}/clinical-source`, payload)),
  compare: (patientId: string, assessmentId: string, otherId: string) => request<ComparabilityResult>(http.get(`/therapist/patients/${patientId}/assessments/${assessmentId}/clinical-stage/comparison/${otherId}`))
}
