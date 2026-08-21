import { http, request } from './http'
import type { Attempt, TrainingFeedbackResult } from '@/types/api'

const audioExtensionByMimeType: Record<string, string> = {
  'audio/ogg': 'ogg',
  'audio/ogg;codecs=opus': 'ogg',
  'audio/webm': 'webm',
  'audio/webm;codecs=opus': 'webm'
}

function audioFilename(file: Blob): string {
  return `training.${audioExtensionByMimeType[file.type] ?? 'webm'}`
}

export const attemptsApi = {
  create(sessionTaskId: string) {
    return request<Attempt>(http.post('/attempts', { session_task_id: sessionTaskId }))
  },
  uploadAudio(attemptId: string, file: Blob) {
    const form = new FormData()
    form.append('audio_file', file, audioFilename(file))
    return request<Attempt>(http.post(`/attempts/${attemptId}/audio`, form))
  },
  analyze(attemptId: string) {
    return request<TrainingFeedbackResult>(http.post(`/attempts/${attemptId}/analyze`))
  }
}
