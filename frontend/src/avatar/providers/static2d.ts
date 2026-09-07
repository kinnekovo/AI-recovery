import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'
import { toUserMessage } from '@/utils/errors'

export class Static2DAvatarProvider implements AvatarProvider {
  kind = 'static_2d' as const
  label = '2D 陪练'
  capabilities = {
    speech: true,
    lipSync: true,
    expression: true,
    streaming: false
  }

  private utterance: SpeechSynthesisUtterance | null = null
  private audio: HTMLAudioElement | null = null
  private mouthTimer: number | null = null
  private stopCurrentAudio: (() => void) | null = null
  private runId = 0

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    if (input.interrupt !== false) this.stop()
    const runId = ++this.runId
    context.update({ state: 'speaking', line: input.text, error: '' })
    this.startMouth(context)
    try {
      if (input.audioUrl) {
        try {
          await this.speakWithAudio(input.audioUrl)
        } catch {
          await this.speakWithFallback(input.text)
        }
      } else if ('speechSynthesis' in window) {
        await this.speakWithBrowserTts(input.text)
      } else {
        await this.silentSpeak(input.text)
      }
    } catch (err) {
      context.update({ state: 'error', error: toUserMessage(err, '数字人语音播放失败') })
    } finally {
      if (this.runId === runId) {
        this.stopMouth(context)
        context.update({ state: 'idle' })
      }
    }
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    context.update({ state })
  }

  stop() {
    this.runId += 1
    this.stopCurrentAudio?.()
    this.stopCurrentAudio = null
    if (this.audio) {
      this.audio.pause()
      this.audio = null
    }
    if (this.utterance && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    this.utterance = null
    this.clearTimer()
  }

  private speakWithAudio(audioUrl: string) {
    return new Promise<void>((resolve, reject) => {
      const audio = new Audio(audioUrl)
      this.audio = audio
      const cleanup = () => {
        audio.onended = null
        audio.onerror = null
        if (this.audio === audio) this.audio = null
        if (this.stopCurrentAudio === stopPlayback) this.stopCurrentAudio = null
      }
      const stopPlayback = () => {
        cleanup()
        resolve()
      }
      this.stopCurrentAudio = stopPlayback
      audio.onended = () => {
        cleanup()
        resolve()
      }
      audio.onerror = () => {
        cleanup()
        reject(new Error('数字人音频无法播放'))
      }
      void audio.play().catch((err) => {
        cleanup()
        reject(err)
      })
    })
  }

  private speakWithFallback(text: string) {
    if ('speechSynthesis' in window) return this.speakWithBrowserTts(text)
    return this.silentSpeak(text)
  }

  private speakWithBrowserTts(text: string) {
    return new Promise<void>((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'zh-CN'
      utterance.rate = 0.88
      utterance.pitch = 1
      utterance.onend = () => resolve()
      utterance.onerror = () => reject(new Error('浏览器 TTS 播放失败'))
      this.utterance = utterance
      window.speechSynthesis.speak(utterance)
    })
  }

  private silentSpeak(text: string) {
    const duration = Math.min(Math.max(text.length * 120, 900), 4200)
    return new Promise<void>((resolve) => window.setTimeout(resolve, duration))
  }

  private startMouth(context: AvatarProviderContext) {
    this.clearTimer()
    this.mouthTimer = window.setInterval(() => {
      context.update({ mouthOpen: Math.random() > 0.45 })
    }, 130)
  }

  private stopMouth(context: AvatarProviderContext) {
    this.clearTimer()
    context.update({ mouthOpen: false })
  }

  private clearTimer() {
    if (this.mouthTimer == null) return
    window.clearInterval(this.mouthTimer)
    this.mouthTimer = null
  }
}
