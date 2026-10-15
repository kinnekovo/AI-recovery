export type AvatarProviderKind = 'static_2d' | 'live2d' | 'three_d' | 'external_streaming' | 'tencent_cloud'

export type AvatarRuntimeState = 'idle' | 'loading_speech' | 'speaking' | 'listening' | 'thinking' | 'encouraging' | 'error'
export type AvatarSpeechSource = 'none' | 'cloud_audio' | 'cloud_text' | 'cloud_custom_text' | 'browser_tts' | 'silent'

export interface AvatarRuntimeSnapshot {
  provider: AvatarProviderKind
  state: AvatarRuntimeState
  line: string
  mouthOpen: boolean
  /** 0--1，来自真实音频能量或降级播放节奏。 */
  mouthEnergy: number
  speechSource: AvatarSpeechSource
  canSpeak: boolean
  error: string
  videoUrl: string | null
  videoStatus: 'idle' | 'queued' | 'running' | 'ready' | 'fallback' | 'failed'
  videoElapsedSeconds: number
}

export interface AvatarSpeakInput {
  text: string
  audioUrl?: string | null
  videoTaskId?: string | null
  interrupt?: boolean
}

export interface AvatarProviderUpdate {
  provider?: AvatarProviderKind
  state?: AvatarRuntimeState
  line?: string
  mouthOpen?: boolean
  mouthEnergy?: number
  speechSource?: AvatarSpeechSource
  error?: string
  videoUrl?: string | null
  videoStatus?: AvatarRuntimeSnapshot['videoStatus']
  videoElapsedSeconds?: number
}

export interface AvatarProviderContext {
  update(update: AvatarProviderUpdate): void
}

export interface AvatarProvider {
  kind: AvatarProviderKind
  label: string
  capabilities: {
    speech: boolean
    lipSync: boolean
    expression: boolean
    streaming: boolean
  }
  prepare?(context: AvatarProviderContext): Promise<void>
  speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void>
  setState(state: AvatarRuntimeState, context: AvatarProviderContext): void
  stop(): void
  dispose?(): void
}
