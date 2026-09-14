<template>
  <section class="page-stack narrow">
    <div class="page-heading">
      <span class="kicker">创建陪伴者</span>
      <h1>上传熟悉的人物形象</h1>
      <p>当前仅创建 2.5D 动态形象；声音复刻功能已暂时隐藏，便于先验收形象效果。</p>
    </div>
    <form v-if="!createdAgent" class="form-panel" @submit.prevent="createPortraitAgent">
      <label>名称<input v-model="form.name" placeholder="妈妈" /></label>
      <label>关系<input v-model="form.relationship" placeholder="母亲" /></label>
      <label>陪伴风格<input v-model="form.personality_style" placeholder="温柔鼓励" /></label>
      <label>
        陪伴者正面照
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="pickAvatar" />
        <small>单人、正面、面部清晰、无遮挡，建议上传胸部以上照片。</small>
      </label>
      <p v-if="avatarChecking" class="success-text">正在本地校验照片…</p>
      <p v-else-if="avatarMessage" class="error-text">{{ avatarMessage }}</p>
      <figure v-if="avatarPreview" class="avatar-upload-preview-wrap">
        <img class="avatar-upload-preview" :src="avatarPreview" alt="陪伴者头像裁剪预览" />
        <figcaption>将以此构图显示在动态陪练中</figcaption>
      </figure>
      <label class="check-line">
        <input v-model="consent" type="checkbox" />
        已确认该形象获得本人授权，仅用于康复训练
      </label>
      <p v-if="error" class="error-text">{{ error }}</p>
      <AppButton variant="primary" :loading="loading">创建 2.5D 形象</AppButton>
    </form>
    <section v-else-if="voiceCloneEnabled" class="form-panel voice-clone-panel" aria-live="polite">
      <span class="kicker">第二步：专属声音</span>
      <h2>按指定文本录一段声音</h2>
      <p>可直接在浏览器朗读，也可上传已录好的文件。更换句子只会重新领取腾讯允许的朗读文本，不会创建新的音色 ID。</p>
      <div class="training-text-wrap">
        <blockquote class="training-text">{{ createdAgent.voice_training_text }}</blockquote>
        <AppButton v-if="!createdAgent.voice_clone_task_id" variant="quiet" :loading="refreshingText" @click="changeTrainingText">
          换一句
        </AppButton>
      </div>
      <label>
        音色性别
        <select v-model="voiceGender" :disabled="Boolean(createdAgent.voice_clone_task_id)">
          <option :value="2">女声</option>
          <option :value="1">男声</option>
        </select>
      </label>
      <div v-if="!createdAgent.voice_clone_task_id" class="voice-input-choice">
        <section>
          <h3>直接朗读</h3>
          <p>允许麦克风后，按上方文字自然朗读；录音会自动转换为腾讯支持的 WAV 文件。</p>
          <div class="button-row">
            <AppButton v-if="!recording" variant="secondary" :disabled="loading" @click="startRecording">开始录音</AppButton>
            <AppButton v-else variant="primary" @click="stopRecording">结束录音（{{ recordingSeconds }} 秒）</AppButton>
          </div>
          <p v-if="recordingMessage" :class="recordingError ? 'error-text' : 'success-text'">{{ recordingMessage }}</p>
        </section>
        <section>
          <h3>上传录音</h3>
          <p>也可以选择已按上方文字录好的文件：WAV、MP3、AAC、M4A，时长 5–15 秒、2MB 以内。</p>
          <label>
            指定文本的录音文件
            <input type="file" accept="audio/wav,audio/mpeg,audio/aac,audio/mp4,.m4a" @change="chooseVoiceFile" />
          </label>
        </section>
      </div>
      <p v-if="voice && !createdAgent.voice_clone_task_id" class="success-text">当前将提交：{{ voice.name }}</p>
      <p v-if="cloneMessage" class="success-text">{{ cloneMessage }}</p>
      <p v-if="error" class="error-text">{{ error }}</p>
      <div class="button-row">
        <AppButton v-if="!createdAgent.voice_clone_task_id" variant="primary" :loading="loading" @click="startVoiceClone">
          检测录音并创建唯一音色
        </AppButton>
        <AppButton v-else variant="secondary" :loading="loading" @click="refreshVoiceStatus">
          查询复刻训练结果
        </AppButton>
        <AppButton variant="quiet" :disabled="createdAgent.generation_status !== 'voice_ready' && createdAgent.generation_status !== 'ready'" @click="finish">
          完成创建
        </AppButton>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import { agentsApi } from '@/api/agents'
import { toUserMessage } from '@/utils/errors'
import { type PortraitAnimationConfig, validatePortrait } from '@/avatar/face/portrait'
import type { Agent } from '@/types/api'

const router = useRouter()
// 声音复刻已保留实现，但在 2.5D 形象验收阶段不展示、不调用。
const voiceCloneEnabled = false
const form = ref({ name: '', relationship: '', personality_style: '温柔鼓励' })
const avatar = ref<File | null>(null)
const avatarConfig = ref<PortraitAnimationConfig | null>(null)
const avatarPreview = ref('')
const avatarChecking = ref(false)
const avatarMessage = ref('')
const voice = ref<File | null>(null)
const voiceGender = ref<1 | 2>(2)
const consent = ref(true)
const loading = ref(false)
const error = ref('')
const cloneMessage = ref('')
const createdAgent = ref<Agent | null>(null)
const refreshingText = ref(false)
const recording = ref(false)
const recordingSeconds = ref(0)
const recordingMessage = ref('')
const recordingError = ref(false)
let mediaRecorder: MediaRecorder | null = null
let microphoneStream: MediaStream | null = null
let recordingTimer: number | null = null
let recordingStartedAt = 0

function pickFile(event: Event): File | null {
  const input = event.target as HTMLInputElement
  return input.files?.[0] || null
}

function chooseVoiceFile(event: Event) {
  voice.value = pickFile(event)
  recordingMessage.value = voice.value ? '已选择上传的录音文件。' : ''
  recordingError.value = false
}

async function pickAvatar(event: Event) {
  const file = pickFile(event)
  avatar.value = null
  avatarConfig.value = null
  avatarMessage.value = ''
  if (avatarPreview.value) URL.revokeObjectURL(avatarPreview.value)
  avatarPreview.value = ''
  if (!file) return
  avatarChecking.value = true
  const validation = await validatePortrait(file)
  avatarChecking.value = false
  if (!validation.config) {
    avatarMessage.value = validation.message || '这张照片暂时不能用于动态陪练。'
    return
  }
  avatar.value = file
  avatarConfig.value = validation.config
  avatarPreview.value = await createCropPreview(file, validation.config.crop)
}

async function createCropPreview(file: File, crop: PortraitAnimationConfig['crop']): Promise<string> {
  const sourceUrl = URL.createObjectURL(file)
  let usesSourceUrl = false
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error('preview_image_load_failed'))
      element.src = sourceUrl
    })
    const canvas = document.createElement('canvas')
    const size = 360
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d')
    if (!context) throw new Error('preview_canvas_unavailable')
    context.drawImage(
      image,
      crop.x * image.naturalWidth,
      crop.y * image.naturalHeight,
      crop.width * image.naturalWidth,
      crop.height * image.naturalHeight,
      0,
      0,
      size,
      size,
    )
    const preview = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    if (preview) return URL.createObjectURL(preview)
    usesSourceUrl = true
    return sourceUrl
  } catch {
    usesSourceUrl = true
    return sourceUrl
  } finally {
    // 成功分支已把位图绘制进 Canvas；失败分支仍需要保留原图 URL。
    if (!usesSourceUrl) URL.revokeObjectURL(sourceUrl)
  }
}

async function createPortraitAgent() {
  error.value = ''
  if (!consent.value) {
    error.value = '请先确认授权'
    return
  }
  if (!avatar.value || !avatarConfig.value) {
    error.value = '请先上传一张通过校验的正面人物照片。'
    return
  }
  loading.value = true
  try {
    const agent = await agentsApi.create({
      ...form.value,
      image_consent_confirmed: true,
      voice_consent_confirmed: false
    })
    await agentsApi.uploadAvatar(agent.id, avatar.value, avatarConfig.value)
    if (voiceCloneEnabled) {
      try {
        createdAgent.value = await agentsApi.getVoiceTrainingText(agent.id)
      } catch (err) {
        error.value = toUserMessage(err, '形象已创建，但暂时无法获取声音复刻朗读文本。')
      }
    } else {
      await agentsApi.setCurrent(agent.id)
      router.push('/agent/list')
    }
  } catch (err) {
    error.value = toUserMessage(err, '创建失败')
  } finally {
    loading.value = false
  }
}

async function changeTrainingText() {
  if (!createdAgent.value) return
  error.value = ''
  cloneMessage.value = ''
  refreshingText.value = true
  try {
    createdAgent.value = await agentsApi.getVoiceTrainingText(createdAgent.value.id, true)
    voice.value = null
    recordingMessage.value = '已换成腾讯下发的新句子，请按新句子重新录音。'
    recordingError.value = false
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法更换朗读文本')
  } finally {
    refreshingText.value = false
  }
}

async function startRecording() {
  error.value = ''
  recordingMessage.value = ''
  recordingError.value = false
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    recordingError.value = true
    recordingMessage.value = '当前浏览器不支持直接录音，请改用“上传录音”。'
    return
  }
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    })
    const chunks: BlobPart[] = []
    mediaRecorder = new MediaRecorder(microphoneStream)
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data)
    }
    mediaRecorder.onstop = async () => {
      const elapsedSeconds = (Date.now() - recordingStartedAt) / 1000
      cleanupRecorder()
      try {
        voice.value = await convertRecordingToWav(new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' }), elapsedSeconds)
        recordingMessage.value = `录音已准备好（${elapsedSeconds.toFixed(1)} 秒），可提交检测。`
      } catch (err) {
        voice.value = null
        recordingError.value = true
        recordingMessage.value = err instanceof Error ? err.message : '录音转换失败，请改用上传录音。'
      }
    }
    recordingStartedAt = Date.now()
    recordingSeconds.value = 0
    recording.value = true
    mediaRecorder.start()
    recordingTimer = window.setInterval(() => {
      recordingSeconds.value = Math.floor((Date.now() - recordingStartedAt) / 1000)
      if (recordingSeconds.value >= 15) stopRecording()
    }, 250)
  } catch (err) {
    cleanupRecorder()
    recordingError.value = true
    recordingMessage.value = toUserMessage(err, '无法使用麦克风；请确认已允许浏览器访问麦克风，或改用上传录音。')
  }
}

function stopRecording() {
  if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
}

function cleanupRecorder() {
  recording.value = false
  if (recordingTimer !== null) window.clearInterval(recordingTimer)
  recordingTimer = null
  microphoneStream?.getTracks().forEach((track) => track.stop())
  microphoneStream = null
  mediaRecorder = null
}

async function convertRecordingToWav(blob: Blob, elapsedSeconds: number): Promise<File> {
  if (elapsedSeconds <= 5 || elapsedSeconds >= 15) {
    throw new Error('录音需要大于 5 秒且小于 15 秒；请重新朗读。')
  }
  const context = new AudioContext()
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer())
    if (decoded.duration <= 5 || decoded.duration >= 15) {
      throw new Error('录音需要大于 5 秒且小于 15 秒；请重新朗读。')
    }
    const wav = encodeMonoWav(decoded, 24000)
    if (wav.size > 2 * 1024 * 1024) throw new Error('录音文件超过 2MB，请缩短录音或改用上传文件。')
    return new File([wav], `voice-clone-${Date.now()}.wav`, { type: 'audio/wav' })
  } finally {
    await context.close()
  }
}

function encodeMonoWav(buffer: AudioBuffer, targetRate: number): Blob {
  const outputLength = Math.ceil(buffer.duration * targetRate)
  const bytes = new ArrayBuffer(44 + outputLength * 2)
  const view = new DataView(bytes)
  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + outputLength * 2, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, targetRate, true)
  view.setUint32(28, targetRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, outputLength * 2, true)
  for (let index = 0; index < outputLength; index += 1) {
    const sourcePosition = (index * buffer.sampleRate) / targetRate
    const left = Math.min(Math.floor(sourcePosition), buffer.length - 1)
    const right = Math.min(left + 1, buffer.length - 1)
    const mix = Array.from({ length: buffer.numberOfChannels }, (_, channel) => {
      const samples = buffer.getChannelData(channel)
      const fraction = sourcePosition - left
      return samples[left] * (1 - fraction) + samples[right] * fraction
    }).reduce((sum, sample) => sum + sample, 0) / buffer.numberOfChannels
    view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, mix)) * 0x7fff, true)
  }
  return new Blob([bytes], { type: 'audio/wav' })
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index))
}

async function startVoiceClone() {
  error.value = ''
  cloneMessage.value = ''
  if (!createdAgent.value || !voice.value) {
    error.value = '请先选择按指定文本录制的声音文件。'
    return
  }
  loading.value = true
  try {
    createdAgent.value = await agentsApi.uploadVoice(createdAgent.value.id, voice.value, voiceGender.value)
    cloneMessage.value = '录音已通过并已创建唯一复刻任务。腾讯云通常需要几分钟训练；请稍后点击“查询复刻训练结果”。'
  } catch (err) {
    error.value = toUserMessage(err, '声音检测或复刻任务创建失败')
  } finally {
    loading.value = false
  }
}

async function refreshVoiceStatus() {
  if (!createdAgent.value) return
  error.value = ''
  cloneMessage.value = ''
  loading.value = true
  try {
    const result = await agentsApi.getVoiceStatus(createdAgent.value.id)
    createdAgent.value = result.agent
    if (result.task_status_code === 2) {
      cloneMessage.value = '专属音色训练完成，已保存唯一音色 ID。现在可以完成创建。'
    } else if (result.task_status_code === 3) {
      error.value = result.error_message || '声音复刻任务未完成。为避免创建多个音色 ID，页面已停止再次提交。'
    } else {
      cloneMessage.value = '声音复刻仍在训练中，请稍后再次查询。'
    }
  } catch (err) {
    error.value = toUserMessage(err, '查询声音复刻任务失败')
  } finally {
    loading.value = false
  }
}

async function finish() {
  if (!createdAgent.value) return
  await agentsApi.setCurrent(createdAgent.value.id)
  router.push('/agent/list')
}

onBeforeUnmount(() => {
  if (avatarPreview.value) URL.revokeObjectURL(avatarPreview.value)
  cleanupRecorder()
})
</script>
