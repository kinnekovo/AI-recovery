import { avatarSessionsApi, type TencentAvatarSession } from '@/api/avatarSessions'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'

export class TencentCloudAvatarProvider implements AvatarProvider {
  kind = 'tencent_cloud' as const
  label = '腾讯云实时数字人'
  capabilities = { speech: true, lipSync: true, expression: true, streaming: true }
  private readonly fallback = new Static2DAvatarProvider()
  private session: TencentAvatarSession | null = null
  private player: HTMLIFrameElement | null = null
  private leaseId: string | null = null
  private agentId: string | null = null
  private active = false
  private connecting: Promise<boolean> | null = null
  private context: AvatarProviderContext | null = null
  private runId = 0
  private soundEnabled = false
  private playerReady = false
  private playerReadyPromise: Promise<boolean> | null = null
  private resolvePlayerReady: ((ready: boolean) => void) | null = null
  private connectionError = ''

  private get speechSource() {
    return this.session?.timbre_bound ? 'cloud_custom_text' as const : 'cloud_text' as const
  }

  constructor(private readonly containerId: string) {
    window.addEventListener('message', this.onPlayerMessage)
  }

  setAgent(agentId: string | null, active = agentId !== null) {
    if (this.agentId === agentId && this.active === active) return
    this.resetSession()
    this.agentId = agentId
    this.active = active
  }

  async prepare(context: AvatarProviderContext): Promise<void> {
    this.context = context
    if (!this.active) return
    if (this.session && this.playerIsMounted()) {
      const playerReady = await this.waitForPlayerReady()
      if (!playerReady) {
        context.update({ error: '腾讯云数字人画面连接超时，请重试。', videoStatus: 'failed' })
        return
      }
      this.markReady(this.session)
      await this.enableSound()
      return
    }
    context.update({
      provider: 'tencent_cloud',
      state: 'idle',
      line: '正在连接腾讯云数字人画面…',
      error: '',
      speechSource: 'cloud_text',
      videoStatus: 'running',
    })
    const connected = await this.connect()
    if (!connected) {
      context.update({
        provider: 'static_2d',
        state: 'error',
        line: '腾讯云数字人暂时没有连接成功，可以刷新后重试。',
        videoStatus: 'failed',
      })
      return
    }
    const playerReady = await this.waitForPlayerReady()
    if (!playerReady) {
      context.update({ error: '腾讯云数字人画面连接超时，请重试。', videoStatus: 'failed' })
      return
    }
    if (this.session) this.markReady(this.session)
    await this.enableSound()
  }

  get isSoundEnabled() {
    return this.soundEnabled
  }

  async enableSound(): Promise<boolean> {
    if (this.soundEnabled) return true
    const playerWindow = this.player?.contentWindow as (Window & {
      enableTencentAvatarSound?: () => Promise<boolean>
    }) | null
    if (!playerWindow?.enableTencentAvatarSound) return false
    try {
      const enabled = await playerWindow.enableTencentAvatarSound()
      this.soundEnabled = enabled
      return enabled
    } catch {
      return false
    }
  }

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    this.context = context
    const runId = ++this.runId
    context.update({ provider: 'tencent_cloud', state: 'loading_speech', line: input.text, error: '', speechSource: this.speechSource, videoStatus: 'running' })
    try {
      const connected = await this.connect()
      if (!connected || !this.leaseId) throw new Error(this.connectionError || '腾讯云数字人会话未能建立。')
      if (runId !== this.runId) return
      if (!this.soundEnabled) {
        const enabled = await this.enableSound()
        if (!enabled) throw new Error('浏览器尚未允许播放声音，请重新进入训练。')
        if (runId !== this.runId) return
      }
      context.update({ provider: 'tencent_cloud', state: 'speaking', line: input.text, speechSource: this.speechSource, videoStatus: 'ready' })
      const startedAt = performance.now()
      const result = await avatarSessionsApi.sendText(this.leaseId, input.text)
      const remainingMs = Math.max(0, result.duration_seconds * 1000 + 500 - (performance.now() - startedAt))
      if (remainingMs) await new Promise((resolve) => window.setTimeout(resolve, remainingMs))
      if (runId === this.runId) context.update({ state: 'idle', mouthOpen: false, mouthEnergy: 0 })
    } catch (error) {
      if (runId === this.runId) {
        const failureMessage = error instanceof Error ? error.message : '腾讯云数字人播报失败，已切换为本机语音示范。'
        this.resetSession()
        // Static2DAvatarProvider starts by resetting the snapshot. Start it
        // first, then restore the cloud failure so the UI never presents the
        // uploaded portrait as a successfully connected realtime avatar.
        const fallbackPlayback = this.fallback.speak(input, context)
        context.update({
          provider: 'static_2d',
          videoStatus: 'failed',
          error: failureMessage,
          line: input.text,
        })
        await fallbackPlayback
      }
    }
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    if (this.session) context.update({ provider: 'tencent_cloud', state })
    else this.fallback.setState(state, context)
  }

  stop() {
    this.runId += 1
    this.fallback.stop()
  }

  dispose() {
    this.resetSession()
    window.removeEventListener('message', this.onPlayerMessage)
  }

  private resetSession() {
    this.stop()
    const leaseId = this.leaseId
    this.session = null
    this.leaseId = null
    this.connecting = null
    this.soundEnabled = false
    this.playerReady = false
    this.connectionError = ''
    this.resolvePlayerReady?.(false)
    this.resolvePlayerReady = null
    this.playerReadyPromise = null
    this.player?.remove()
    this.player = null
    if (leaseId) void avatarSessionsApi.close(leaseId).catch(() => undefined)
  }

  private async connect(): Promise<boolean> {
    const container = document.getElementById(this.containerId)
    if (!this.active || !container) return false
    if (this.session) {
      if (!this.playerIsMounted()) {
        this.soundEnabled = false
        this.mountPlayer(this.session.play_stream_addr)
      }
      return true
    }
    this.connecting ||= this.createSession()
    return this.connecting
  }

  private async createSession(): Promise<boolean> {
    let lease: TencentAvatarSession | null = null
    try {
      const response = await avatarSessionsApi.create(this.agentId, 'tencent')
      if (response.provider !== 'tencent') throw new Error('腾讯云数字人会话响应类型不正确。')
      lease = response
      if (!lease.play_stream_addr.startsWith('webrtc://')) throw new Error('当前测试播放器只支持腾讯云 WebRTC 播放地址。')
      this.soundEnabled = false
      this.mountPlayer(lease.play_stream_addr)
      this.session = lease
      this.leaseId = lease.id
      this.connectionError = ''
      return true
    } catch (error) {
      if (lease?.id) void avatarSessionsApi.close(lease.id).catch(() => undefined)
      this.connectionError = error instanceof Error ? error.message : '腾讯云数字人连接失败。'
      this.context?.update({ error: this.connectionError, videoStatus: 'failed' })
      return false
    } finally {
      this.connecting = null
    }
  }

  private mountPlayer(playStreamAddr: string) {
    const container = document.getElementById(this.containerId)
    if (!container) throw new Error('训练页数字人播放区域尚未就绪。')
    this.player?.remove()
    container.replaceChildren()
    this.playerReady = false
    this.resolvePlayerReady?.(false)
    this.playerReadyPromise = new Promise((resolve) => { this.resolvePlayerReady = resolve })
    const iframe = document.createElement('iframe')
    iframe.title = '腾讯云数字人实时画面'
    iframe.allow = 'autoplay; fullscreen'
    iframe.src = `/tencent-avatar/webrtc-player.html?url=${encodeURIComponent(playStreamAddr)}`
    container.appendChild(iframe)
    this.player = iframe
  }

  private playerIsMounted() {
    const container = document.getElementById(this.containerId)
    return Boolean(container && this.player?.isConnected && this.player.parentElement === container)
  }

  private markReady(lease: TencentAvatarSession) {
    this.context?.update({
      provider: 'tencent_cloud',
      line: lease.timbre_bound
        ? '腾讯云数字人已绑定专属声音。'
        : '腾讯云数字人已连接，当前使用默认声音。',
      error: '',
      speechSource: lease.timbre_bound ? 'cloud_custom_text' : 'cloud_text',
      videoStatus: 'ready',
    })
  }

  private readonly onPlayerMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin || event.source !== this.player?.contentWindow) return
    const message = event.data as { type?: string; status?: string } | null
    if (message?.type !== 'tencent-avatar-player') return
    if (message.status === 'error') {
      this.connectionError = '腾讯云数字人画面连接失败，请刷新后重试。'
      this.context?.update({ error: this.connectionError, videoStatus: 'failed' })
      this.resolvePlayerReady?.(false)
      this.resolvePlayerReady = null
    }
    if (message.status === 'ready') {
      this.playerReady = true
      this.resolvePlayerReady?.(true)
      this.resolvePlayerReady = null
    }
    if (message.status === 'unmuted') {
      this.soundEnabled = true
    }
  }

  private async waitForPlayerReady(): Promise<boolean> {
    if (this.playerReady) return true
    if (!this.playerReadyPromise) return false
    return Promise.race([
      this.playerReadyPromise,
      new Promise<boolean>((resolve) => window.setTimeout(() => resolve(false), 20_000)),
    ])
  }

}
