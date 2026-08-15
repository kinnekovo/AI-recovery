import { http, request } from './http'
import type { TodayTraining, TrainingRecommendation, TrainingSession, TrainingSessionCreatePayload } from '@/types/api'

export const trainingApi = {
  types() {
    return request<string[]>(http.get('/training/types'))
  },
  today() {
    return request<TodayTraining>(http.get('/training/today'))
  },
  recommendation() {
    return request<TrainingRecommendation>(http.get('/training/recommendation'))
  },
  createSession(payload: TrainingSessionCreatePayload | 'repeat' | 'scenario') {
    const body = typeof payload === 'string' ? { type: payload } : payload
    return request<TrainingSession>(http.post('/training/session', body))
  },
  getSession(sessionId: string) {
    return request<TrainingSession>(http.get(`/training/session/${sessionId}`))
  }
}
