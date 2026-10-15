import { http } from '@/api/http'
import { avatarSessionsApi, type TencentAvatarSession } from '@/api/avatarSessions'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'

type AudioContextConstructor = typeof AudioContext

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
  private audioContext: AudioContext | null = null
  private runId = 0
  private soundEnabled = false
  private resolveSoundGate: ((enabled: boolean) => void) | null = null
  private connectionError = ''

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
    context.update({
      provider: 'tencent_cloud',
      state: 'idle',
      line: '正在连接腾讯云数字人画面…',
      error: '',
      speechSource: 'cloud_audio',
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
    }
  }

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    this.context = context
    if (!input.audioUrl) {
      context.update({ provider: 'static_2d' })
      return this.fallback.speak(input, context)
    }
    const runId = ++this.runId
    context.update({ provider: 'tencent_cloud', state: 'loading_speech', line: input.text, error: '', speechSource: 'cloud_audio', videoStatus: 'running' })
    try {
      const [connected, pcm] = await Promise.all([this.connect(), this.decodeToPcm(input.audioUrl)])
      if (!connected || !this.leaseId) throw new Error(this.connectionError || '腾讯云数字人会话未能建立。')
      if (runId !== this.runId) return
      if (!this.soundEnabled) {
        context.update({ line: '数字人画面已连接，请点击画面中的“开启声音”继续。', state: 'loading_speech' })
        const enabled = await this.waitForSound()
        if (!enabled || runId !== this.runId) return
      }
      context.update({ provider: 'tencent_cloud', state: 'speaking', speechSource: 'cloud_audio', videoStatus: 'ready' })
      const startedAt = performance.now()
      const result = await avatarSessionsApi.sendAudio(
        this.leaseId,
        pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength) as ArrayBuffer,
      )
      const remainingMs = Math.max(0, result.duration_seconds * 1000 + 500 - (performance.now() - startedAt))
      if (remainingMs) await new Promise((resolve) => window.setTimeout(resolve, remainingMs))
      if (runId === this.runId) context.update({ state: 'idle', mouthOpen: false, mouthEnergy: 0 })
    } catch (error) {
      if (runId === this.runId) {
        const failureMessage = error instanceof Error ? error.message : '腾讯云数字人播报失败，已切换为纯语音示范。'
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
    this.connectionError = ''
    this.resolveSoundGate?.(false)
    this.resolveSoundGate = null
    this.player?.remove()
    this.player = null
    if (leaseId) void avatarSessionsApi.close(leaseId).catch(() => undefined)
    if (this.audioContext) void this.audioContext.close().catch(() => undefined)
    this.audioContext = null
  }

  private async connect(): Promise<boolean> {
    if (this.session) return true
    if (!this.active || !document.getElementById(this.containerId)) return false
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
      this.context?.update({ provider: 'tencent_cloud', line: '腾讯云数字人已准备好。首次使用请在画面中点击“开启声音”。', error: '', speechSource: 'cloud_audio', videoStatus: 'ready' })
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
    container.replaceChildren()
    const iframe = document.createElement('iframe')
    iframe.title = '腾讯云数字人实时画面'
    iframe.allow = 'autoplay; fullscreen'
    iframe.src = `/tencent-avatar/webrtc-player.html?url=${encodeURIComponent(playStreamAddr)}`
    container.appendChild(iframe)
    this.player = iframe
  }

  private readonly onPlayerMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin || event.source !== this.player?.contentWindow) return
    const message = event.data as { type?: string; status?: string } | null
    if (message?.type !== 'tencent-avatar-player') return
    if (message.status === 'error') this.context?.update({ error: '腾讯云数字人画面连接失败，请刷新后重试。' })
    if (message.status === 'unmuted') {
      this.soundEnabled = true
      this.resolveSoundGate?.(true)
      this.resolveSoundGate = null
    }
  }

  private waitForSound(): Promise<boolean> {
    if (this.soundEnabled) return Promise.resolve(true)
    return new Promise((resolve) => { this.resolveSoundGate = resolve })
  }

  private async decodeToPcm(audioUrl: string): Promise<Int16Array> {
    const response = await http.get<Blob>(audioUrl.startsWith('/api') ? audioUrl.slice(4) : audioUrl, { responseType: 'blob' })
    const AudioContextClass = (window.AudioContext || (window as Window & { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext) as AudioContextConstructor | undefined
    if (!AudioContextClass) throw new Error('当前浏览器不支持腾讯云数字人音频驱动。')
    this.audioContext ||= new AudioContextClass()
    const decoded = await this.audioContext.decodeAudioData(await response.data.arrayBuffer())
    const targetRate = 16000
    const frameCount = Math.max(1, Math.ceil(decoded.duration * targetRate))
    const offline = new OfflineAudioContext(1, frameCount, targetRate)
    const source = offline.createBufferSource()
    source.buffer = decoded
    source.connect(offline.destination)
    source.start(0)
    const rendered = await offline.startRendering()
    const samples = rendered.getChannelData(0)
    const pcm = new Int16Array(samples.length)
    for (let index = 0; index < samples.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, samples[index]))
      pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }
    return pcm
  }

}
