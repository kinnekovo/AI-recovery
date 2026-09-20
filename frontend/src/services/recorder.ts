export class RecorderService {
  private recorder: MediaRecorder | null = null
  private stream: MediaStream | null = null
  private chunks: Blob[] = []
  private mimeType = ''

  private pickMimeType(): string {
    // Edge and Chromium reliably play and upload WebM/Opus. Prefer it over Ogg
    // so the local preview and the server transcoder receive the same container.
    const supportedTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
    return supportedTypes.find((type) => MediaRecorder.isTypeSupported(type)) ?? ''
  }

  async start(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      throw new Error('当前浏览器不支持录音，请使用最新版 Edge 或 Chrome。')
    }
    this.cleanup()
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    const track = stream.getAudioTracks()[0]
    if (!track || !track.enabled || track.readyState !== 'live') {
      stream.getTracks().forEach((item) => item.stop())
      throw new Error('未检测到可用麦克风，请检查浏览器麦克风权限和系统输入设备。')
    }
    this.chunks = []
    this.mimeType = this.pickMimeType()
    this.stream = stream
    this.recorder = new MediaRecorder(stream, this.mimeType ? { mimeType: this.mimeType } : undefined)
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data)
    }
    this.recorder.start(250)
  }

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const recorder = this.recorder
      if (!recorder || recorder.state === 'inactive') {
        reject(new Error('录音尚未开始'))
        return
      }
      recorder.onerror = () => {
        this.cleanup()
        reject(new Error('录音设备发生错误，请重新开始录音。'))
      }
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || this.mimeType || 'audio/webm'
        const blob = new Blob(this.chunks, { type: mimeType })
        this.cleanup()
        if (blob.size < 1024) {
          reject(new Error('没有采集到足够的声音，请确认麦克风权限后再录一次。'))
          return
        }
        resolve(blob)
      }
      recorder.requestData()
      recorder.stop()
    })
  }

  dispose() {
    this.cleanup()
  }

  private cleanup() {
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = null
    this.recorder = null
    this.chunks = []
  }
}
