export class RecorderService {
  private recorder: MediaRecorder | null = null
  private chunks: Blob[] = []
  private mimeType = ''

  private pickMimeType(): string {
    const supportedTypes = ['audio/ogg;codecs=opus', 'audio/webm;codecs=opus', 'audio/webm']
    return supportedTypes.find((type) => MediaRecorder.isTypeSupported(type)) ?? ''
  }

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    this.chunks = []
    this.mimeType = this.pickMimeType()
    this.recorder = new MediaRecorder(stream, this.mimeType ? { mimeType: this.mimeType } : undefined)
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data)
    }
    this.recorder.start()
  }

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.recorder) {
        reject(new Error('录音尚未开始'))
        return
      }
      this.recorder.onstop = () => {
        const mimeType = this.recorder?.mimeType || this.mimeType || 'audio/webm'
        this.recorder?.stream.getTracks().forEach((track) => track.stop())
        resolve(new Blob(this.chunks, { type: mimeType }))
      }
      this.recorder.stop()
    })
  }
}
