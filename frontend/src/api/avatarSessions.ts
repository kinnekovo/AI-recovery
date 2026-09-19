import { http, request } from './http'

export interface AliyunAvatarSession {
  id: string
  session_id: string
  rtc_params: Record<string, string | number | null>
}

export const avatarSessionsApi = {
  create(agentId: string) {
    return request<AliyunAvatarSession>(http.post('/avatar/sessions', { agent_id: agentId }))
  },
  close(sessionId: string) {
    return request<{ closed: boolean }>(http.delete(`/avatar/sessions/${sessionId}`))
  }
}
