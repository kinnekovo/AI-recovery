import { http } from '@/api/http'
import { avatarSessionsApi, type TencentAvatarSession } from '@/api/avatarSessions'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'
import type { TencentIVH } from '@/types/tencent-avatar'

type AudioContextConstructor = typeof AudioContext

/**
 * Tencent's cloud-rendering H5 SDK is distributed as an official browser JS
 * file rather than an npm package. The URL is intentionally configurable so a
 * licensed SDK file can be loaded without committing a vendor binary here.
 */
export class TencentCloudAvatarProvider implements AvatarProvider {
  kind = 'tencent_cloud' as const
  label = '腾讯云实时数字人'
  capabilities = { speech: true, lipSync: true, expression: true, streaming: true }
  private readonly fallback = new Static2DAvatarProvider()
  private ivh: TencentIVH | null = null
  private leaseId: string | null = null
  private agentId: string | null = null
  private connecting: Promise<boolean> | null = null
  private context: AvatarProviderContext | null = null
  private audioContext: AudioContext | null = null
  private runId = 0

  constructor(private readonly containerId: string) {}

  setAgent(agentId: string | null) {
    if (this.agentId === agentId) return
    this.dispose()
    this.agentId = agentId
  }

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    this.context = context
    if (!input.audioUrl || !(await this.connect())) {
      context.update({ provider: 'static_2d' })
      return this.fallback.speak(input, context)
    }
    const runId = ++this.runId
    context.update({ provider: 'tencent_cloud', state: 'loading_speech', line: input.text, error: '', speechSource: 'cloud_audio', videoStatus: 'idle' })
    try {
      const pcm = await this.decodeToPcm(input.audioUrl)
      if (runId !== this.runId || !this.ivh) return
      context.update({ provider: 'tencent_cloud', state: 'speaking', speechSource: 'cloud_audio' })
      await this.sendPcm(pcm, runId)
    } catch (error) {
      if (runId === this.runId) {
        this.dispose()
        context.update({ provider: 'static_2d', error: error instanceof Error ? error.message : '腾讯云数字人播报失败，已切换本地形象。' })
        await this.fallback.speak(input, context)
      }
    }
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    if (this.ivh) context.update({ provider: 'tencent_cloud', state })
    else this.fallback.setState(state, context)
  }

  stop() {
    this.runId += 1
    this.fallback.stop()
    try { this.ivh?.stop() } catch { /* SDK best effort */ }
  }

  dispose() {
    this.stop()
    const ivh = this.ivh
    const leaseId = this.leaseId
    this.ivh = null
    this.leaseId = null
    this.connecting = null
    try { void ivh?.closeSession() } catch { /* SDK best effort */ }
    if (leaseId) void avatarSessionsApi.close(leaseId).catch(() => undefined)
    if (this.audioContext) void this.audioContext.close().catch(() => undefined)
    this.audioContext = null
  }

  private async connect(): Promise<boolean> {
    if (this.ivh) return true
    if (!this.agentId || !document.getElementById(this.containerId)) return false
    this.connecting ||= this.createSession()
    return this.connecting
  }

  private async createSession(): Promise<boolean> {
    let lease: TencentAvatarSession | null = null
    try {
      const response = await avatarSessionsApi.create(this.agentId!, 'tencent')
      if (response.provider !== 'tencent') throw new Error('腾讯云数字人会话响应类型不正确。')
      lease = response
      const sdk = await loadTencentSdk()
      sdk.init({
        sign: lease.sign,
        element: `#${this.containerId}`,
        assetVirtualmanKey: lease.asset_virtualman_key,
      })
      sdk.on('socketStatus', (event: { status?: string }) => {
        if (event?.status === 'close') this.context?.update({ error: '腾讯云数字人连接已断开，已准备本地回退。' })
      })
      sdk.on('socket', (event: { speakStatus?: string; errorCode?: number; errorMessage?: string }) => this.onSocket(event))
      sdk.on('error', (event: { message?: string }) => this.context?.update({ error: event?.message || '腾讯云数字人连接异常。' }))
      const created = await sdk.createSessionByAsset({ driverType: lease.driver_type, userId: lease.user_id })
      if (!created) throw new Error('腾讯云未返回有效数字人会话。')
      const started = await sdk.startSession()
      if (!started) throw new Error('腾讯云数字人会话启动失败。')
      this.ivh = sdk
      this.leaseId = lease.id
      this.context?.update({ provider: 'tencent_cloud', line: '腾讯云数字人已准备好。', error: '', speechSource: 'cloud_audio' })
      return true
    } catch {
      if (lease?.id) void avatarSessionsApi.close(lease.id).catch(() => undefined)
      return false
    } finally {
      this.connecting = null
    }
  }

  private onSocket(event: { speakStatus?: string; errorCode?: number; errorMessage?: string }) {
    if (event.errorCode && event.errorCode !== 0) {
      this.context?.update({ error: event.errorMessage || '腾讯云数字人驱动失败。' })
      return
    }
    if (event.speakStatus === 'AudioStart') this.context?.update({ provider: 'tencent_cloud', state: 'speaking' })
    if (event.speakStatus === 'AudioOver') this.context?.update({ provider: 'tencent_cloud', state: 'idle', mouthOpen: false, mouthEnergy: 0 })
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

  private async sendPcm(pcm: Int16Array, runId: number) {
    if (!this.ivh) return
    const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
    const chunkSize = 5120
    let seq = 1
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      if (runId !== this.runId || !this.ivh) return
      const chunk = bytes.slice(offset, offset + chunkSize)
      this.ivh.play({ command: 'audio', data: bytesToBase64(chunk), seq, isFinal: false })
      seq += 1
      await new Promise((resolve) => window.setTimeout(resolve, 120))
    }
    if (runId === this.runId && this.ivh) this.ivh.play({ command: 'audio', data: '', seq, isFinal: true })
  }
}

let sdkPromise: Promise<TencentIVH> | null = null

function loadTencentSdk(): Promise<TencentIVH> {
  if (window.IVH) return Promise.resolve(window.IVH)
  if (sdkPromise) return sdkPromise
  const sdkUrl = String(import.meta.env.VITE_TENCENT_IVH_SDK_URL || '').trim()
  if (!sdkUrl) return Promise.reject(new Error('未配置腾讯云 H5 SDK 地址，当前使用本地数字人。'))
  sdkPromise = new Promise<TencentIVH>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = sdkUrl
    script.async = true
    script.onload = () => window.IVH ? resolve(window.IVH) : reject(new Error('腾讯云 H5 SDK 未暴露 IVH 对象。'))
    script.onerror = () => reject(new Error('腾讯云 H5 SDK 加载失败，当前使用本地数字人。'))
    document.head.appendChild(script)
  })
  return sdkPromise
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const block = 0x8000
  for (let offset = 0; offset < bytes.length; offset += block) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + block))
  }
  return window.btoa(binary)
}
