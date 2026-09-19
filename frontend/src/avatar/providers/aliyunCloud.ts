import { createCloudAvatar, IRequestToRespondType, TYVoiceChatMode, type IAvatarInitConfig } from 'lm-avatar-chat-sdk/cloud'
import { avatarSessionsApi } from '@/api/avatarSessions'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'

type CloudAvatar = ReturnType<typeof createCloudAvatar>

/**
 * Cloud rendering remains optional. A failed or disabled session deliberately
 * falls back to the local provider so training and recording never stop.
 */
export class AliyunCloudAvatarProvider implements AvatarProvider {
  kind = 'external_streaming' as const
  label = '阿里云实时数字人'
  capabilities = { speech: true, lipSync: true, expression: true, streaming: true }
  private readonly fallback = new Static2DAvatarProvider()
  private avatar: CloudAvatar | null = null
  private leaseId: string | null = null
  private agentId: string | null = null
  private connecting: Promise<boolean> | null = null
  private context: AvatarProviderContext | null = null

  constructor(private readonly containerId: string) {}

  setAgent(agentId: string | null) {
    if (this.agentId === agentId) return
    this.dispose()
    this.agentId = agentId
  }

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    this.context = context
    if (await this.connect()) {
      context.update({ provider: 'external_streaming', state: 'speaking', line: input.text, error: '', speechSource: 'cloud_audio', videoStatus: 'idle' })
      try {
        this.avatar?.requestToRespond(IRequestToRespondType.transcript, input.text)
        return
      } catch {
        this.dispose()
      }
    }
    context.update({ provider: 'static_2d' })
    return this.fallback.speak(input, context)
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    if (this.avatar) context.update({ provider: 'external_streaming', state })
    else this.fallback.setState(state, context)
  }

  stop() {
    this.fallback.stop()
    try { this.avatar?.interrupt() } catch { /* SDK ignores invalid interruption states */ }
  }

  dispose() {
    this.fallback.stop()
    const avatar = this.avatar
    const leaseId = this.leaseId
    this.avatar = null
    this.leaseId = null
    this.connecting = null
    try { avatar?.exit() } catch { /* best-effort browser cleanup */ }
    if (leaseId) void avatarSessionsApi.close(leaseId).catch(() => undefined)
  }

  private async connect(): Promise<boolean> {
    if (this.avatar) return true
    if (!this.agentId || !document.getElementById(this.containerId)) return false
    this.connecting ||= this.createSession()
    return this.connecting
  }

  private async createSession(): Promise<boolean> {
    try {
      const lease = await avatarSessionsApi.create(this.agentId!)
      const init = {
        ...camelRtcParams(lease.rtc_params),
        rootContainer: `#${this.containerId}`,
        sessionId: lease.session_id,
        ignoreAudioInput: true,
      } as IAvatarInitConfig
      const avatar = createCloudAvatar(init)
      avatar.onStateChanged?.((state: string) => this.onStateChanged(state))
      avatar.onErrorReceived?.((error: { message?: string }) => this.context?.update({ error: error.message || '阿里云数字人连接异常。' }))
      avatar.onFirstFrameReceived?.(() => this.context?.update({ provider: 'external_streaming', state: 'idle', error: '' }))
      avatar.start({ mode: TYVoiceChatMode.tap2talk })
      this.avatar = avatar
      this.leaseId = lease.id
      this.context?.update({ provider: 'external_streaming', line: '数字人已准备好。', error: '', speechSource: 'cloud_audio' })
      return true
    } catch {
      return false
    }
  }

  private onStateChanged(state: string) {
    const mapped: Record<string, AvatarRuntimeState> = { StandBy: 'idle', Listening: 'listening', Thinking: 'thinking', Responding: 'speaking' }
    const runtimeState = mapped[state]
    if (runtimeState) this.context?.update({ provider: 'external_streaming', state: runtimeState })
  }
}

function camelRtcParams(params: Record<string, string | number | null>) {
  return {
    appId: params.app_id,
    channel: params.channel,
    timestamp: params.timestamp,
    token: params.token,
    nonce: params.nonce,
    clientUserId: params.client_user_id,
    serverUserId: params.server_user_id,
    avatarUserId: params.avatar_user_id,
    gslb: params.gslb,
  }
}
