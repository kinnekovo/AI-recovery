export class RecorderService {
  private recorder: MediaRecorder | null = null
  private chunks: Blob[] = []

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    this.chunks = []
    this.recorder = new MediaRecorder(stream)
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
        this.recorder?.stream.getTracks().forEach((track) => track.stop())
        resolve(new Blob(this.chunks, { type: 'audio/webm' }))
      }
      this.recorder.stop()
    })
  }
}
