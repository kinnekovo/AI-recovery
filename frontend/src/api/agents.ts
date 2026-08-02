import { http, request } from './http'
import type { Agent } from '@/types/api'

export const agentsApi = {
  create(payload: {
    name: string
    relationship: string
    personality_style: string
    image_consent_confirmed: boolean
    voice_consent_confirmed: boolean
  }) {
    return request<Agent>(http.post('/agents', payload))
  },
  list() {
    return request<Agent[]>(http.get('/agents'))
  },
  setCurrent(agentId: string) {
    return request(http.put(`/users/current-agent/${agentId}`))
  },
  uploadAvatar(agentId: string, file: File) {
    const form = new FormData()
    form.append('avatar_file', file)
    return request<Agent>(http.post(`/agents/${agentId}/avatar`, form))
  },
  uploadVoice(agentId: string, file: File) {
    const form = new FormData()
    form.append('audio_file', file)
    return request<Agent>(http.post(`/agents/${agentId}/voice`, form))
  },
  generateWelcome(agentId: string) {
    return request<{ agent: Agent; audio_url: string }>(http.post(`/agents/${agentId}/welcome-audio`))
  }
}
