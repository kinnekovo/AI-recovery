<template>
  <section class="recorder-panel">
    <div>
      <strong>{{ recording ? '正在录音' : audioBlob ? '录音已就绪' : '准备录音' }}</strong>
      <p>{{ hint }}</p>
      <small v-if="recording">已录 {{ elapsedSeconds }} 秒，建议说完一句后再结束。</small>
      <small v-else-if="audioBlob">可以先试听，觉得不清楚就重新录一遍。</small>
    </div>
    <div class="recorder-actions">
      <AppButton v-if="!recording" variant="primary" @click="start">开始录音</AppButton>
      <AppButton v-else variant="secondary" @click="stop">结束录音</AppButton>
    </div>
    <p v-if="error" class="form-feedback error">{{ error }}</p>
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
import { toUserMessage } from '@/utils/errors'

const emit = defineEmits<{ recorded: [blob: Blob]; recordingState: [recording: boolean]; recorderError: [message: string] }>()
const recorder = new RecorderService()
const recording = ref(false)
const audioBlob = ref<Blob | null>(null)
const audioUrl = ref('')
const elapsedSeconds = ref(0)
const error = ref('')
let timer: ReturnType<typeof window.setInterval> | null = null
const hint = computed(() => {
  if (recording.value) return '请自然说话，尽量把屏幕上的句子说完整。'
  if (audioBlob.value) return '录音已经保存到本页，还没有上传评分。'
  return '请在安静环境中完成，开始前把麦克风靠近一些。'
})

async function start() {
  revokeAudioUrl()
  audioBlob.value = null
  error.value = ''
  try {
    await recorder.start()
    elapsedSeconds.value = 0
    timer = window.setInterval(() => {
      elapsedSeconds.value += 1
    }, 1000)
    recording.value = true
    emit('recordingState', true)
  } catch (err) {
    error.value = toUserMessage(err, '无法开始录音，请检查浏览器麦克风权限。')
    emit('recorderError', error.value)
  }
}

async function stop() {
  clearTimer()
  try {
    audioBlob.value = await recorder.stop()
    audioUrl.value = URL.createObjectURL(audioBlob.value)
    recording.value = false
    emit('recordingState', false)
    emit('recorded', audioBlob.value)
  } catch (err) {
    recording.value = false
    error.value = toUserMessage(err, '录音保存失败，请重新录一遍。')
    emit('recordingState', false)
    emit('recorderError', error.value)
  }
}

function revokeAudioUrl() {
  if (!audioUrl.value) return
  URL.revokeObjectURL(audioUrl.value)
  audioUrl.value = ''
}

function clearTimer() {
  if (!timer) return
  window.clearInterval(timer)
  timer = null
}

onBeforeUnmount(() => {
  clearTimer()
  revokeAudioUrl()
})
</script>
