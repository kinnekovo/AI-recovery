<template>
  <section class="voice-setting" aria-labelledby="voice-setting-title">
    <div class="voice-setting-heading">
      <div>
        <span class="voice-setting-kicker">陪伴声音</span>
        <h3 id="voice-setting-title">{{ title }}</h3>
      </div>
      <span class="voice-status" :class="`voice-status-${agent.voice_clone_status}`">{{ statusLabel }}</span>
    </div>

    <p class="voice-setting-summary">{{ summary }}</p>

    <template v-if="agent.voice_clone_status === 'ready'">
      <audio v-if="agent.voice_sample_url" class="voice-audio" controls :src="agent.voice_sample_url">
        当前浏览器不支持播放音频。
      </audio>
      <p class="voice-help">跟读训练会在实时数字人会话中直接使用这套声音，不会额外生成音频文件。</p>
    </template>

    <template v-else-if="isProcessing">
      <div class="voice-progress" role="status">
        <span class="voice-progress-dot" />
        <span>{{ progressLabel }}</span>
      </div>
      <AppButton variant="secondary" :loading="loadingStatus" @click="refreshStatus">刷新进度</AppButton>
    </template>

    <template v-else-if="expanded">
      <p v-if="displayError" class="voice-inline-error">{{ displayError }}</p>
      <div class="voice-script">
        <span>自由录音，不核对固定台词</span>
        <p>请让 {{ agent.name }} 用平常的语气，自然说一段连续、清楚的话。</p>
      </div>
      <ul class="voice-guidance">
        <li>建议录制 15–20 秒，可以讲一段回忆、问候或日常生活。</li>
        <li>保持安静，只录这一位熟悉的人，嘴离麦克风约一拳距离。</li>
        <li>支持 WAV、MP3、M4A、AAC、WMA、ASF，建议不超过 5MB（接口上限 20MB）。</li>
      </ul>
      <label class="voice-file-label">
        <span>选择熟悉之人的录音</span>
        <input type="file" accept="audio/*,.wav,.mp3,.m4a,.aac,.wma,.asf" @change="selectFile" />
      </label>
      <audio v-if="localAudioUrl" class="voice-audio" controls :src="localAudioUrl">
        当前浏览器不支持播放音频。
      </audio>
      <fieldset class="voice-gender-group">
        <legend>声音类型</legend>
        <label><input v-model="voiceGender" type="radio" :value="1" /> 男声</label>
        <label><input v-model="voiceGender" type="radio" :value="2" /> 女声</label>
      </fieldset>
      <label class="check-line voice-consent">
        <input v-model="consentConfirmed" type="checkbox" />
        <span>我确认已获得这位录音者本人的授权，同意将录音提交腾讯云创建专属音色，并用于患者的康复训练口播。</span>
      </label>
      <AppButton
        variant="primary"
        :loading="uploading"
        :disabled="!selectedFile || !consentConfirmed"
        @click="submitVoice"
      >提交自由录音并开始复刻</AppButton>
    </template>

    <AppButton v-else variant="secondary" @click="expanded = true">创建专属声音</AppButton>
    <p v-if="localError" class="voice-inline-error" role="alert">{{ localError }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import AppButton from '@/components/common/AppButton.vue'
import { agentsApi } from '@/api/agents'
import type { Agent } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const props = defineProps<{ agent: Agent }>()
const emit = defineEmits<{ updated: [agent: Agent] }>()

const expanded = ref(props.agent.voice_clone_status === 'failed')
const selectedFile = ref<File | null>(null)
const localAudioUrl = ref('')
const consentConfirmed = ref(false)
const voiceGender = ref<1 | 2>(props.agent.voice_gender ?? (props.agent.avatar_gender === 'MALE' ? 1 : 2))
const uploading = ref(false)
const loadingStatus = ref(false)
const localError = ref('')

const isProcessing = computed(() => ['detecting', 'training'].includes(props.agent.voice_clone_status))
const title = computed(() => props.agent.voice_clone_status === 'ready' ? '熟悉的声音已就绪' : '上传熟悉之人的声音')
const statusLabel = computed(() => ({
  pending: '未创建', detecting: '检测录音', training: '正在复刻', ready: '可以使用', failed: '需要重试'
}[props.agent.voice_clone_status] ?? '未创建'))
const summary = computed(() => {
  if (props.agent.voice_clone_status === 'ready') return '之后生成的数字人示范语，会使用这套个性化音色。'
  if (props.agent.voice_clone_status === 'detecting') return '腾讯云正在检查录音环境、音质和有效时长。'
  if (props.agent.voice_clone_status === 'training') return '录音已经通过检测，腾讯云正在创建专属音色。'
  if (props.agent.voice_clone_status === 'failed') return '上一次没有完成。查看原因后，可以重新提交一段录音。'
  return '上传一段已获本人授权的亲友录音，让数字人用患者熟悉的声音陪伴训练。'
})
const progressLabel = computed(() => props.agent.voice_clone_status === 'detecting' ? '正在检测录音，通常需要几分钟。' : '正在生成专属声音，请稍后刷新。')
const displayError = computed(() => {
  const error = props.agent.voice_clone_error ?? ''
  if (error.includes('文本准确率')) {
    return '上一次录音按固定文本检测，因此没有通过。现在可直接重新提交自由录音，不再核对朗读文字。'
  }
  return voiceCloneErrorMessage(error)
})

function voiceCloneErrorMessage(error: string, canRefresh = false) {
  if (error.includes('LimitExceeded') || error.includes('超过配额限制') || error.includes('无可用定制资产')) {
    const nextStep = canRefresh ? '购买后点击“刷新进度”，当前录音无需重新上传。' : '购买后重新提交这段录音。'
    return `当前腾讯云账号没有可用的“声音复刻-极速版”定制配额。你已购买的数字人交互并发不包含这项配额；${nextStep}`
  }
  return error
}

function selectFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null
  selectedFile.value = file
  localError.value = ''
  if (localAudioUrl.value) URL.revokeObjectURL(localAudioUrl.value)
  localAudioUrl.value = file ? URL.createObjectURL(file) : ''
  if (file && file.size > 20 * 1024 * 1024) localError.value = '录音文件不能超过 20MB。'
}

async function submitVoice() {
  if (!selectedFile.value || !consentConfirmed.value) return
  if (selectedFile.value.size > 20 * 1024 * 1024) {
    localError.value = '录音文件不能超过 20MB。'
    return
  }
  uploading.value = true
  localError.value = ''
  try {
    emit('updated', await agentsApi.uploadVoice(props.agent.id, selectedFile.value, voiceGender.value, true))
  } catch (err) {
    localError.value = voiceCloneErrorMessage(toUserMessage(err, '提交声音复刻失败'))
  } finally {
    uploading.value = false
  }
}

async function refreshStatus() {
  loadingStatus.value = true
  localError.value = ''
  try {
    const result = await agentsApi.getVoiceStatus(props.agent.id)
    emit('updated', result.agent)
  } catch (err) {
    localError.value = voiceCloneErrorMessage(toUserMessage(err, '查询声音复刻进度失败'), true)
  } finally {
    loadingStatus.value = false
  }
}

onBeforeUnmount(() => {
  if (localAudioUrl.value) URL.revokeObjectURL(localAudioUrl.value)
})
</script>

<style scoped>
.voice-setting { display: grid; gap: 14px; padding-top: 16px; border-top: 1px solid #dce7e1; }
.voice-setting-heading { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
.voice-setting-heading h3 { margin: 3px 0 0; font-size: 1.05rem; line-height: 1.35; }
.voice-setting-kicker { color: #288466; font-size: .82rem; font-weight: 800; letter-spacing: .04em; }
.voice-setting-summary, .voice-help { margin: 0; color: #5b6d65; line-height: 1.65; }
.voice-help { font-size: .9rem; }
.voice-status { flex: 0 0 auto; padding: 5px 9px; border-radius: 999px; background: #eef3f0; color: #52645c; font-size: .78rem; font-weight: 800; }
.voice-status-ready { background: #e4f5ec; color: #176a4a; }
.voice-status-detecting, .voice-status-training { background: #eaf1ff; color: #1f4fb8; }
.voice-status-failed { background: #fff0ec; color: #b42318; }
.voice-script { display: grid; gap: 8px; padding: 15px 16px; border: 1px solid #dce7e1; border-radius: 8px; background: #f3f8f5; }
.voice-script span { color: #288466; font-size: .82rem; font-weight: 800; }
.voice-script p { margin: 0; color: #20302a; font-size: 1rem; font-weight: 700; line-height: 1.75; }
.voice-guidance { margin: 0; padding-left: 20px; color: #5b6d65; font-size: .9rem; line-height: 1.65; }
.voice-file-label { gap: 7px; }
.voice-audio { width: 100%; height: 42px; }
.voice-gender-group { display: flex; flex-wrap: wrap; gap: 18px; margin: 0; padding: 0; border: 0; }
.voice-gender-group legend { margin-bottom: 8px; color: #40524b; font-weight: 750; }
.voice-gender-group label { display: flex; grid-template-columns: none; align-items: center; gap: 7px; }
.voice-gender-group input { width: auto; }
.voice-consent { align-items: start; padding: 12px; border-radius: 8px; background: #fff8ed; font-size: .88rem; line-height: 1.55; }
.voice-progress { display: flex; align-items: center; gap: 9px; color: #294c40; font-weight: 700; }
.voice-progress-dot { width: 9px; height: 9px; border-radius: 50%; background: #2563eb; box-shadow: 0 0 0 5px #eaf1ff; }
.voice-inline-error { margin: 0; color: #b42318; line-height: 1.55; }
</style>
