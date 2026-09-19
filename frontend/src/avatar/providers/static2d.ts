import { http } from '@/api/http'
import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'
import { toUserMessage } from '@/utils/errors'

/** Local, no-cost fallback used while Alibaba Cloud is unavailable. */
export class Static2DAvatarProvider implements AvatarProvider {
  kind = 'static_2d' as const
  label = '2D 陪练'
  capabilities = { speech: true, lipSync: true, expression: true, streaming: false }
  private audio: HTMLAudioElement | null = null
  private utterance: SpeechSynthesisUtterance | null = null
  private objectUrl: string | null = null
  private mouthTimer: number | null = null
  private runId = 0

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    this.stop()
    const runId = ++this.runId
    context.update({ provider: 'static_2d', state: input.audioUrl ? 'loading_speech' : 'speaking', line: input.text, error: '', videoUrl: null, videoStatus: 'idle', videoElapsedSeconds: 0 })
    try {
      if (input.audioUrl) await this.playCloudAudio(input.audioUrl, context, runId)
      else await this.playFallback(input.text, context, runId)
    } catch (error) {
      if (runId === this.runId) context.update({ state: 'error', error: toUserMessage(error, '数字人语音播放失败') })
    } finally {
      if (runId === this.runId) {
        this.stopMouth(context)
        context.update({ state: 'idle' })
      }
    }
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    context.update({ provider: 'static_2d', state })
  }

  stop() {
    this.runId += 1
    this.audio?.pause()
    this.audio = null
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl)
    this.objectUrl = null
    if (this.utterance && 'speechSynthesis' in window) window.speechSynthesis.cancel()
    this.utterance = null
    if (this.mouthTimer != null) window.clearInterval(this.mouthTimer)
    this.mouthTimer = null
  }

  private async playCloudAudio(url: string, context: AvatarProviderContext, runId: number) {
    const response = await http.get<Blob>(url.startsWith('/api') ? url.slice(4) : url, { responseType: 'blob' })
    if (runId !== this.runId) return
    this.objectUrl = URL.createObjectURL(response.data)
    await new Promise<void>((resolve, reject) => {
      const audio = new Audio(this.objectUrl!)
      this.audio = audio
      audio.onended = () => resolve()
      audio.onerror = () => reject(new Error('数字人音频无法播放'))
      context.update({ state: 'speaking', speechSource: 'cloud_audio' })
      this.startMouth(context)
      void audio.play().catch(reject)
    })
  }

  private async playFallback(text: string, context: AvatarProviderContext, runId: number) {
    if (!('speechSynthesis' in window)) {
      context.update({ speechSource: 'silent' })
      await new Promise<void>((resolve) => window.setTimeout(resolve, Math.min(Math.max(text.length * 120, 900), 4200)))
      return
    }
    context.update({ speechSource: 'browser_tts' })
    this.startMouth(context)
    await new Promise<void>((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'zh-CN'
      utterance.rate = 0.88
      utterance.onend = () => resolve()
      utterance.onerror = () => reject(new Error('浏览器 TTS 播放失败'))
      this.utterance = utterance
      if (runId === this.runId) window.speechSynthesis.speak(utterance)
      else resolve()
    })
  }

  private startMouth(context: AvatarProviderContext) {
    const started = performance.now()
    this.mouthTimer = window.setInterval(() => {
      const energy = Math.max(0.04, Math.min(0.68, Math.max(0, Math.sin((performance.now() - started) / 65)) * 0.7))
      context.update({ mouthOpen: energy > 0.2, mouthEnergy: energy })
    }, 60)
  }

  private stopMouth(context: AvatarProviderContext) {
    if (this.mouthTimer != null) window.clearInterval(this.mouthTimer)
    this.mouthTimer = null
    context.update({ mouthOpen: false, mouthEnergy: 0 })
  }
}
