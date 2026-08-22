import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'

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

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    if (input.interrupt !== false) this.stop()
    context.update({ state: 'speaking', line: input.text, error: '' })
    this.startMouth(context)
    try {
      if (input.audioUrl) {
        await this.speakWithAudio(input.audioUrl)
      } else if ('speechSynthesis' in window) {
        await this.speakWithBrowserTts(input.text)
      } else {
        await this.silentSpeak(input.text)
      }
    } catch (err) {
      context.update({ state: 'error', error: err instanceof Error ? err.message : '数字人语音播放失败' })
    } finally {
      this.stopMouth(context)
      context.update({ state: 'idle' })
    }
  }

  setState(state: AvatarRuntimeState, context: AvatarProviderContext) {
    context.update({ state })
  }

  stop() {
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
      this.audio = new Audio(audioUrl)
      this.audio.onended = () => resolve()
      this.audio.onerror = () => reject(new Error('数字人音频无法播放'))
      void this.audio.play().catch(reject)
    })
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
