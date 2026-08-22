<template>
  <section class="recorder-panel">
    <div>
      <strong>{{ recording ? '正在录音' : audioBlob ? '录音已就绪' : '准备录音' }}</strong>
      <p>{{ hint }}</p>
    </div>
    <div class="recorder-actions">
      <AppButton v-if="!recording" variant="primary" @click="start">开始录音</AppButton>
      <AppButton v-else variant="secondary" @click="stop">结束录音</AppButton>
    </div>
    <div v-if="audioUrl" class="audio-review">
      <span>本次录音</span>
      <audio :src="audioUrl" controls></audio>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import AppButton from '@/components/common/AppButton.vue'
import { RecorderService } from '@/services/recorder'

const emit = defineEmits<{ recorded: [blob: Blob]; recordingState: [recording: boolean] }>()
const recorder = new RecorderService()
const recording = ref(false)
const audioBlob = ref<Blob | null>(null)
const audioUrl = ref('')
const hint = computed(() => (recording.value ? '请自然说话，结束后系统会保存本次尝试。' : '请在安静环境中完成。'))

async function start() {
  revokeAudioUrl()
  audioBlob.value = null
  await recorder.start()
  recording.value = true
  emit('recordingState', true)
}

async function stop() {
  audioBlob.value = await recorder.stop()
  audioUrl.value = URL.createObjectURL(audioBlob.value)
  recording.value = false
  emit('recordingState', false)
  emit('recorded', audioBlob.value)
}

function revokeAudioUrl() {
  if (!audioUrl.value) return
  URL.revokeObjectURL(audioUrl.value)
  audioUrl.value = ''
}

onBeforeUnmount(revokeAudioUrl)
</script>
