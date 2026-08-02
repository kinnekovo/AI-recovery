export function playAudio(url: string): void {
  const audio = new Audio(url)
  audio.play()
}
