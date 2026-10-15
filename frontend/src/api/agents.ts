import { http, request } from './http'
import type { Agent } from '@/types/api'
import type { PortraitAnimationConfig } from '@/avatar/face/portrait'

export const agentsApi = {
  create(payload: {
    name: string
    relationship: string
    personality_style: string
    avatar_gender: 'MALE' | 'FEMALE'
    image_consent_confirmed: boolean
    voice_consent_confirmed: boolean
  }) {
    return request<Agent>(http.post('/agents', payload))
  },
  list() {
    return request<Agent[]>(http.get('/agents'))
  },
  remove(agentId: string) {
    return request<{ current_agent_id: string | null }>(http.delete(`/agents/${agentId}`))
  },
  setCurrent(agentId: string) {
    return request(http.put(`/users/current-agent/${agentId}`))
  },
  uploadAvatar(agentId: string, file: File, animationConfig?: PortraitAnimationConfig | null) {
    const form = new FormData()
    form.append('avatar_file', file)
    if (animationConfig) form.append('animation_config', JSON.stringify(animationConfig))
    return request<Agent>(http.post(`/agents/${agentId}/avatar`, form))
  },
  getVoiceTrainingText(agentId: string, refresh = false) {
    return request<Agent>(http.post(`/agents/${agentId}/voice-training-text`, null, { params: { refresh } }))
  },
  syncAliyunAvatar(agentId: string) {
    return request<Agent>(http.post(`/agents/${agentId}/aliyun-avatar/sync`))
  },
  submitTencentAvatar(agentId: string, photoVersion: 0 | 1 = 0) {
    return request<Agent>(http.post(`/agents/${agentId}/tencent-avatar/submit`, null, { params: { photo_version: photoVersion } }))
  },
  refreshTencentAvatar(agentId: string) {
    return request<Agent>(http.post(`/agents/${agentId}/tencent-avatar/status`))
  },
  uploadVoice(agentId: string, file: File, voiceGender: 1 | 2) {
    const form = new FormData()
    form.append('audio_file', file)
    form.append('voice_gender', String(voiceGender))
    return request<Agent>(http.post(`/agents/${agentId}/voice`, form))
  },
  getVoiceStatus(agentId: string) {
    return request<{ agent: Agent; task_status: string; task_status_code: number; error_message: string | null }>(
      http.post(`/agents/${agentId}/voice-status`)
    )
  },
  generateWelcome(agentId: string) {
    return request<{ agent: Agent; audio_url: string }>(http.post(`/agents/${agentId}/welcome-audio`))
  },
  revokeConsent(agentId: string, consentType: 'image' | 'voice') {
    return request<{ id: string }>(
      http.post('/consents/revoke', {
        agent_id: agentId,
        consent_type: consentType
      })
    )
  }
}
