import { computed, onBeforeUnmount, reactive } from 'vue'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarRuntimeSnapshot, AvatarRuntimeState, AvatarProviderUpdate } from '@/avatar/types'

export function useAvatarRuntime(provider: AvatarProvider = new Static2DAvatarProvider()) {
  const snapshot = reactive<AvatarRuntimeSnapshot>({
    provider: provider.kind,
    state: 'idle',
    line: '我会陪你慢慢练。准备好了就开始。',
    mouthOpen: false,
    mouthEnergy: 0,
    speechSource: 'none',
    canSpeak: provider.capabilities.speech,
    error: '',
    videoUrl: null,
    videoStatus: 'idle',
    videoElapsedSeconds: 0
  })

  const context = {
    update(update: AvatarProviderUpdate) {
      Object.assign(snapshot, update)
    }
  }

  const isBusy = computed(() => snapshot.state === 'loading_speech' || snapshot.state === 'speaking' || snapshot.state === 'thinking')

  async function prepare() {
    await provider.prepare?.(context)
  }

  async function speak(text: string, audioUrl?: string | null, videoTaskId?: string | null) {
    await provider.speak({ text, audioUrl, videoTaskId, interrupt: true }, context)
  }

  function listen(line = '我在听，你可以按自己的节奏说。') {
    provider.stop()
    provider.setState('listening', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.error = ''
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  function think(line = '我正在整理这次训练结果。') {
    provider.stop()
    provider.setState('thinking', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.error = ''
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  function encourage(line: string) {
    provider.stop()
    provider.setState('encouraging', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.error = ''
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  function idle(line = '我会陪你慢慢练。准备好了就开始。') {
    provider.stop()
    provider.setState('idle', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.error = ''
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  function fail(line: string) {
    provider.stop()
    provider.setState('error', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.error = line
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  function setState(state: AvatarRuntimeState, line: string) {
    if (state === 'listening') listen(line)
    else if (state === 'thinking') think(line)
    else if (state === 'encouraging') encourage(line)
    else if (state === 'error') fail(line)
    else idle(line)
  }

  function stop() {
    provider.stop()
    snapshot.mouthOpen = false
    snapshot.mouthEnergy = 0
    snapshot.videoUrl = null
    snapshot.videoStatus = 'idle'
    snapshot.videoElapsedSeconds = 0
  }

  onBeforeUnmount(() => {
    stop()
    provider.dispose?.()
  })

  return {
    snapshot,
    isBusy,
    prepare,
    speak,
    listen,
    think,
    encourage,
    idle,
    fail,
    setState,
    stop
  }
}
