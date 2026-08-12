import { http, request } from './http'
import type { TrainingRecommendation, TrainingSession } from '@/types/api'

export const trainingApi = {
  types() {
    return request<string[]>(http.get('/training/types'))
  },
  today() {
    return request<{ plan_id: string; title: string; status: string; items_count: number }>(http.get('/training/today'))
  },
  recommendation() {
    return request<TrainingRecommendation>(http.get('/training/recommendation'))
  },
  createSession(type: 'repeat' | 'scenario') {
    return request<TrainingSession>(http.post('/training/session', { type }))
  },
  getSession(sessionId: string) {
    return request<TrainingSession>(http.get(`/training/session/${sessionId}`))
  }
}
