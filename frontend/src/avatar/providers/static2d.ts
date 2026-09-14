import type { AvatarProvider, AvatarProviderContext, AvatarRuntimeState, AvatarSpeakInput } from '@/avatar/types'
import { http } from '@/api/http'
import { avatarVideosApi } from '@/api/avatarVideos'
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
  private video: HTMLVideoElement | null = null
  private audioObjectUrl: string | null = null
  private mouthTimer: number | null = null
  private mouthFrame: number | null = null
  private stopCurrentAudio: (() => void) | null = null
  private audioRequest: AbortController | null = null
  private videoObjectUrl: string | null = null
  private runId = 0

  async speak(input: AvatarSpeakInput, context: AvatarProviderContext): Promise<void> {
    if (input.interrupt !== false) this.stop()
    const runId = ++this.runId
    context.update({ state: input.audioUrl ? 'loading_speech' : 'speaking', line: input.text, error: '', videoUrl: null, videoStatus: input.videoTaskId ? 'queued' : 'idle', videoElapsedSeconds: 0 })
    if (!input.audioUrl) this.startMouth(context)
    try {
      if (input.audioUrl) {
        try {
          if (input.videoTaskId) {
            // The rendered MP4 already contains the exact driving WAV. Keep the
            // image quiet while it renders, then start picture and sound together.
            const videoUrl = await this.waitForVideo(input.videoTaskId, context, runId)
            if (videoUrl && this.runId === runId) {
              try {
                await this.speakWithVideo(videoUrl, context, runId)
              } catch {
                if (this.runId !== runId) return
                context.update({ videoStatus: 'fallback' })
                await this.speakWithAudio(input.audioUrl, context, runId)
              }
            } else {
              context.update({ videoStatus: 'fallback' })
              await this.speakWithAudio(input.audioUrl, context, runId)
            }
          } else {
            await this.speakWithAudio(input.audioUrl, context, runId)
          }
        } catch {
          if (this.runId !== runId) return
          context.update({ state: 'speaking', speechSource: 'browser_tts' })
          this.startMouth(context)
          await this.speakWithFallback(input.text)
        }
      } else if ('speechSynthesis' in window) {
        context.update({ speechSource: 'browser_tts' })
        await this.speakWithBrowserTts(input.text)
      } else {
        context.update({ speechSource: 'silent' })
        await this.silentSpeak(input.text)
      }
    } catch (err) {
      context.update({ state: 'error', error: toUserMessage(err, '数字人语音播放失败') })
    } finally {
      if (this.runId === runId) {
        this.stopMouth(context)
        context.update({ state: 'idle', videoUrl: null, videoElapsedSeconds: 0 })
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
    this.audioRequest?.abort()
    this.audioRequest = null
    if (this.audio) {
      this.audio.pause()
      this.audio = null
    }
    if (this.video) {
      this.video.pause()
      this.video = null
    }
    if (this.audioObjectUrl) {
      URL.revokeObjectURL(this.audioObjectUrl)
      this.audioObjectUrl = null
    }
    if (this.videoObjectUrl) {
      URL.revokeObjectURL(this.videoObjectUrl)
      this.videoObjectUrl = null
    }
    if (this.utterance && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    this.utterance = null
    this.clearTimer()
  }

  private async speakWithAudio(audioUrl: string, context: AvatarProviderContext, runId: number) {
    const url = audioUrl.startsWith('/api') ? audioUrl.slice(4) : audioUrl
    const controller = new AbortController()
    this.audioRequest = controller
    const response = await http.get<Blob>(url, { responseType: 'blob', signal: controller.signal })
    if (this.audioRequest === controller) this.audioRequest = null
    if (this.runId !== runId) return
    const objectUrl = URL.createObjectURL(response.data)
    this.audioObjectUrl = objectUrl
    return new Promise<void>((resolve, reject) => {
      const audio = new Audio(objectUrl)
      this.audio = audio
      let audioContext: AudioContext | null = null
      let analyser: AnalyserNode | null = null
      let source: MediaElementAudioSourceNode | null = null
      const cleanup = () => {
        if (this.mouthFrame != null) {
          window.cancelAnimationFrame(this.mouthFrame)
          this.mouthFrame = null
        }
        source?.disconnect()
        analyser?.disconnect()
        void audioContext?.close()
        audio.onended = null
        audio.onerror = null
        if (this.audio === audio) this.audio = null
        if (this.audioObjectUrl === objectUrl) {
          URL.revokeObjectURL(objectUrl)
          this.audioObjectUrl = null
        }
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
      context.update({ state: 'speaking', speechSource: 'cloud_audio' })
      void audio.play().catch((err) => {
        cleanup()
        reject(err)
      })
      try {
        audioContext = new AudioContext()
        analyser = audioContext.createAnalyser()
        analyser.fftSize = 512
        analyser.smoothingTimeConstant = 0.78
        source = audioContext.createMediaElementSource(audio)
        source.connect(analyser)
        analyser.connect(audioContext.destination)
        const samples = new Uint8Array(analyser.fftSize)
        let energy = 0
        const updateMouth = () => {
          if (!analyser || audio.paused || audio.ended) return
          analyser.getByteTimeDomainData(samples)
          let total = 0
          for (const value of samples) total += Math.abs(value - 128)
          const raw = total / samples.length / 128
          const target = Math.min(1, Math.max(0, (raw - 0.015) * 7))
          energy += (target - energy) * (target > energy ? 0.45 : 0.18)
          context.update({ mouthOpen: energy > 0.18, mouthEnergy: energy })
          this.mouthFrame = window.requestAnimationFrame(updateMouth)
        }
        void audioContext.resume().then(updateMouth)
      } catch {
        this.startMouth(context)
      }
    })
  }

  private async waitForVideo(taskId: string, context: AvatarProviderContext, runId: number): Promise<string | null> {
    const startedAt = performance.now()
    // 512px SadTalker is asynchronous by design. Match the backend's 15-minute
    // timeout so a healthy long prompt is never treated as failed in the UI.
    const timeoutMs = 900_000
    while (this.runId === runId && performance.now() - startedAt < timeoutMs) {
      try {
        const task = await avatarVideosApi.get(taskId)
        const elapsed = Math.floor((performance.now() - startedAt) / 1000)
        if (task.status === 'succeeded' && task.video_url) {
          context.update({ videoStatus: 'ready', videoElapsedSeconds: elapsed })
          return task.video_url
        }
        if (task.status === 'failed') {
          context.update({ videoStatus: 'failed', videoElapsedSeconds: elapsed })
          return null
        }
        context.update({ videoStatus: task.status === 'running' ? 'running' : 'queued', videoElapsedSeconds: elapsed })
      } catch {
        context.update({ videoStatus: 'fallback' })
        return null
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, 1000))
    }
    if (this.runId === runId) context.update({ videoStatus: 'fallback' })
    return null
  }

  private async speakWithVideo(videoUrl: string, context: AvatarProviderContext, runId: number): Promise<void> {
    const url = videoUrl.startsWith('/api') ? videoUrl.slice(4) : videoUrl
    const response = await http.get<Blob>(url, { responseType: 'blob' })
    if (this.runId !== runId) return
    const objectUrl = URL.createObjectURL(response.data)
    this.videoObjectUrl = objectUrl
    return new Promise<void>((resolve, reject) => {
      const video = document.createElement('video')
      video.src = objectUrl
      video.playsInline = true
      this.video = video
      const cleanup = () => {
        video.pause()
        video.onended = null
        video.onerror = null
        if (this.video === video) this.video = null
        if (this.stopCurrentAudio === stopPlayback) this.stopCurrentAudio = null
        if (this.videoObjectUrl === objectUrl) {
          URL.revokeObjectURL(objectUrl)
          this.videoObjectUrl = null
        }
      }
      video.onended = () => {
        cleanup()
        resolve()
      }
      video.onerror = () => {
        cleanup()
        reject(new Error('动态形象视频无法播放'))
      }
      const stopPlayback = () => {
        cleanup()
        resolve()
      }
      this.stopCurrentAudio = stopPlayback
      context.update({ state: 'speaking', speechSource: 'cloud_audio', videoUrl: objectUrl, videoStatus: 'ready' })
      void video.play().catch((err) => {
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
    const startedAt = performance.now()
    this.mouthTimer = window.setInterval(() => {
      const elapsed = (performance.now() - startedAt) / 1000
      const syllable = Math.max(0, Math.sin(elapsed * 15.5))
      const phrase = 0.58 + Math.sin(elapsed * 3.1) * 0.22
      const energy = Math.max(0.04, Math.min(0.68, syllable * phrase))
      context.update({ mouthOpen: energy > 0.2, mouthEnergy: energy })
    }, 60)
  }

  private stopMouth(context: AvatarProviderContext) {
    this.clearTimer()
    context.update({ mouthOpen: false, mouthEnergy: 0 })
  }

  private clearTimer() {
    if (this.mouthTimer == null) return
    window.clearInterval(this.mouthTimer)
    this.mouthTimer = null
  }
}
