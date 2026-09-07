import { http, request } from './http'
import type {
  AvatarSpeech,
  AvatarSpeechPayload,
  TodayTraining,
  TrainingRecommendation,
  TrainingSession,
  TrainingSessionCreatePayload
} from '@/types/api'

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
  createAvatarSpeech(payload: AvatarSpeechPayload) {
    return request<AvatarSpeech>(http.post('/training/avatar-speech', payload))
  },
  getSession(sessionId: string) {
    return request<TrainingSession>(http.get(`/training/session/${sessionId}`))
  }
}
