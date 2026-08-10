import { http, request } from './http'
import type {
  AttemptEvaluationBatch,
  AttemptEvaluationInput,
  EvaluationMetric,
  EvaluationMetricCategory,
  ProcessTrend
} from '@/types/api'

export const evaluationsApi = {
  listMetrics(category?: EvaluationMetricCategory) {
    return request<EvaluationMetric[]>(
      http.get('/evaluations/metrics', {
        params: category ? { category } : undefined
      })
    )
  },
  listAttemptEvaluations(attemptId: string) {
    return request<AttemptEvaluationBatch>(http.get(`/evaluations/attempts/${attemptId}`))
  },
  saveAttemptEvaluations(attemptId: string, items: AttemptEvaluationInput[]) {
    return request<AttemptEvaluationBatch>(http.post(`/evaluations/attempts/${attemptId}`, { items }))
  },
  processTrend(limit = 20) {
    return request<ProcessTrend>(http.get('/evaluations/process-trend', { params: { limit } }))
  }
}
