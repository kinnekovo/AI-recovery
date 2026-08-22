export type AvatarProviderKind = 'static_2d' | 'live2d' | 'three_d' | 'external_streaming'

export type AvatarRuntimeState = 'idle' | 'speaking' | 'listening' | 'thinking' | 'encouraging' | 'error'

export interface AvatarRuntimeSnapshot {
  provider: AvatarProviderKind
  state: AvatarRuntimeState
  line: string
  mouthOpen: boolean
  canSpeak: boolean
  error: string
}

export interface AvatarSpeakInput {
  text: string
  audioUrl?: string | null
  interrupt?: boolean
}

export interface AvatarProviderUpdate {
  state?: AvatarRuntimeState
  line?: string
  mouthOpen?: boolean
  error?: string
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
  speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void>
  setState(state: AvatarRuntimeState, context: AvatarProviderContext): void
  stop(): void
}
