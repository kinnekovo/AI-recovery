import { computed, onBeforeUnmount, reactive } from 'vue'
import { Static2DAvatarProvider } from '@/avatar/providers/static2d'
import type { AvatarProvider, AvatarRuntimeSnapshot, AvatarRuntimeState, AvatarProviderUpdate } from '@/avatar/types'

export function useAvatarRuntime(provider: AvatarProvider = new Static2DAvatarProvider()) {
  const snapshot = reactive<AvatarRuntimeSnapshot>({
    provider: provider.kind,
    state: 'idle',
    line: '我会陪你慢慢练。准备好了就开始。',
    mouthOpen: false,
    canSpeak: provider.capabilities.speech,
    error: ''
  })

  const context = {
    update(update: AvatarProviderUpdate) {
      Object.assign(snapshot, update)
    }
  }

  const isBusy = computed(() => snapshot.state === 'speaking' || snapshot.state === 'thinking')

  async function speak(text: string, audioUrl?: string | null) {
    await provider.speak({ text, audioUrl, interrupt: true }, context)
  }

  function listen(line = '我在听，你可以按自己的节奏说。') {
    provider.stop()
    provider.setState('listening', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.error = ''
  }

  function think(line = '我正在整理这次训练结果。') {
    provider.stop()
    provider.setState('thinking', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.error = ''
  }

  function encourage(line: string) {
    provider.stop()
    provider.setState('encouraging', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.error = ''
  }

  function idle(line = '我会陪你慢慢练。准备好了就开始。') {
    provider.stop()
    provider.setState('idle', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.error = ''
  }

  function fail(line: string) {
    provider.stop()
    provider.setState('error', context)
    snapshot.line = line
    snapshot.mouthOpen = false
    snapshot.error = line
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
  }

  onBeforeUnmount(stop)

  return {
    snapshot,
    isBusy,
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
