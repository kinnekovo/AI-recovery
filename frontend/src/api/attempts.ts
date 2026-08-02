import { http, request } from './http'
import type { Attempt, ScoreResult } from '@/types/api'

export const attemptsApi = {
  create(sessionTaskId: string) {
    return request<Attempt>(http.post('/attempts', { session_task_id: sessionTaskId }))
  },
  uploadAudio(attemptId: string, file: Blob) {
    const form = new FormData()
    form.append('audio_file', file, 'training.webm')
    return request<Attempt>(http.post(`/attempts/${attemptId}/audio`, form))
  },
  analyze(attemptId: string) {
    return request<ScoreResult>(http.post(`/attempts/${attemptId}/analyze`))
  }
}
