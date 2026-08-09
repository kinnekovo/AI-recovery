import { http, request } from './http'
import type {
  AssessmentCompare,
  AssessmentCreatePayload,
  AssessmentSession,
  AssessmentType
} from '@/types/api'

export const assessmentApi = {
  create(payload: AssessmentCreatePayload) {
    return request<AssessmentSession>(http.post('/assessment', payload))
  },
  history(assessmentType?: AssessmentType) {
    return request<AssessmentSession[]>(
      http.get('/assessment/history', {
        params: assessmentType ? { assessment_type: assessmentType } : undefined
      })
    )
  },
  compare(baselineId?: string, currentId?: string) {
    return request<AssessmentCompare>(
      http.get('/assessment/compare', {
        params: {
          ...(baselineId ? { baseline_id: baselineId } : {}),
          ...(currentId ? { current_id: currentId } : {})
        }
      })
    )
  }
}
