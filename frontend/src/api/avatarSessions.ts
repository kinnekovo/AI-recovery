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
  play_stream_addr: string
  protocol: 'webrtc' | 'trtc' | 'rtmp' | string
}

export interface TencentAvatarAudioResult {
  sent_bytes: number
  duration_seconds: number
}

export interface AvatarSpeechResult {
  text: string
  audio_file_id: string
  audio_url: string
  provider: string
  fallback: boolean
  cached: boolean
}

function createAvatarSession(agentId: string, provider?: 'aliyun'): Promise<AliyunAvatarSession>
function createAvatarSession(agentId: string | null, provider: 'tencent'): Promise<TencentAvatarSession>
function createAvatarSession(agentId: string | null, provider: 'aliyun' | 'tencent' = 'aliyun') {
  return request<AliyunAvatarSession | TencentAvatarSession>(http.post(
    '/avatar/sessions',
    { agent_id: agentId, provider },
    { timeout: 135_000 },
  )) as Promise<AliyunAvatarSession | TencentAvatarSession>
}

export const avatarSessionsApi = {
  create: createAvatarSession,
  close(sessionId: string) {
    return request<{ closed: boolean }>(http.delete(`/avatar/sessions/${sessionId}`))
  },
  sendAudio(sessionId: string, pcm: ArrayBuffer) {
    return request<TencentAvatarAudioResult>(http.post(`/avatar/sessions/${sessionId}/audio`, pcm, {
      headers: { 'Content-Type': 'application/octet-stream' },
      timeout: 120_000,
    }))
  },
  generateSpeech(agentId: string | null, text: string) {
    return request<AvatarSpeechResult>(http.post('/avatar/sessions/speech', { agent_id: agentId, text }, { timeout: 60_000 }))
  }
}
