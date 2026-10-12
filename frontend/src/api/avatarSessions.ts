import { http, request } from './http'

export interface AvatarSessionBase {
  id: string
  provider: 'aliyun' | 'tencent'
  session_id: string
}

export interface AliyunAvatarSession extends AvatarSessionBase {
  provider: 'aliyun'
  rtc_params: Record<string, string | number | null>
}

export interface TencentAvatarSession extends AvatarSessionBase {
  provider: 'tencent'
  sign: string
  asset_virtualman_key: string
  user_id: string
  protocol: 'webrtc' | 'trtc' | 'rtmp' | string
  driver_type: number
}

function createAvatarSession(agentId: string): Promise<AliyunAvatarSession>
function createAvatarSession(agentId: string, provider: 'aliyun'): Promise<AliyunAvatarSession>
function createAvatarSession(agentId: string, provider: 'tencent'): Promise<TencentAvatarSession>
function createAvatarSession(agentId: string, provider: 'aliyun' | 'tencent' = 'aliyun') {
  return request<AliyunAvatarSession | TencentAvatarSession>(http.post('/avatar/sessions', { agent_id: agentId, provider })) as Promise<AliyunAvatarSession | TencentAvatarSession>
}

export const avatarSessionsApi = {
  create: createAvatarSession,
  close(sessionId: string) {
    return request<{ closed: boolean }>(http.delete(`/avatar/sessions/${sessionId}`))
  }
}
