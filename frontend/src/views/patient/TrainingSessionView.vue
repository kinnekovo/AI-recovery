<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">{{ groupLabel }}</span>
      <h1>{{ task?.task_template.title || '准备训练' }}</h1>
      <p>{{ task?.task_template.instruction || '正在生成训练会话。' }}</p>
    </div>
    <AvatarCoachPanel v-if="task" :snapshot="avatar.snapshot" :avatar-url="currentAgent?.avatar_url" title="数字人陪练中" compact>
      <template #actions>
        <button class="app-button secondary avatar-action-button" type="button" :disabled="avatar.isBusy.value" @click="() => speakCurrentTask()">
          {{ avatar.isBusy.value ? '正在示范' : '听数字人示范' }}
        </button>
      </template>
    </AvatarCoachPanel>
    <section v-if="task" class="task-panel">
      <div v-if="tasks.length > 1" class="session-step-strip">
        <span v-for="(item, index) in tasks" :key="item.id" :class="{ active: index === currentTaskIndex, done: index < currentTaskIndex }">
          {{ index + 1 }}
        </span>
      </div>
      <div class="task-target">
        <span>{{ task.task_template.content_level }} · {{ task.task_template.autonomy_level }}</span>
        <h2>{{ task.task_template.target_text }}</h2>
        <p v-if="task.task_template.scene_prompt">场景：{{ task.task_template.scene_prompt }}</p>
      </div>
      <div class="patient-trial-hints" aria-label="训练前确认">
        <span>安静一点</span>
        <span>看清句子</span>
        <span>说完再停</span>
      </div>
      <RecorderPanel @recorded="handleRecorded" @recording-state="handleRecordingState" @recorder-error="handleRecorderError" />
      <p v-if="status" class="success-text">{{ status }}</p>
      <p v-if="error" class="error-text">{{ error }}</p>
      <AppButton variant="primary" :disabled="!recordedBlob" :loading="loading" @click="submitAttempt">
        {{ currentTaskIndex + 1 < tasks.length ? '上传并进入下一项' : '上传录音并生成反馈' }}
      </AppButton>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AvatarCoachPanel from '@/components/avatar/AvatarCoachPanel.vue'
import AppButton from '@/components/common/AppButton.vue'
import RecorderPanel from '@/components/training/RecorderPanel.vue'
import { attemptsApi } from '@/api/attempts'
import { trainingApi } from '@/api/training'
import { useAvatarRuntime } from '@/composables/useAvatarRuntime'
import { useAgentStore } from '@/stores/agent'
import { useTrainingStore } from '@/stores/training'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const store = useTrainingStore()
const agentStore = useAgentStore()
const avatar = useAvatarRuntime()
const type = computed(() => route.params.type as 'repeat' | 'scenario')
const tasks = computed(() => store.currentSession?.session_tasks || [])
const currentTaskIndex = ref(0)
const task = computed(() => tasks.value[currentTaskIndex.value])
const groupLabel = computed(() => {
  if (tasks.value.length > 1) return `今日任务组 ${currentTaskIndex.value + 1}/${tasks.value.length}`
  return type.value === 'repeat' ? '跟读训练' : '场景表达'
})
const recordedBlob = ref<Blob | null>(null)
const loading = ref(false)
const status = ref('')
const error = ref('')
const currentAgent = computed(() =>
  agentStore.agents.find((agent) => agent.id === store.currentSession?.agent_id) || agentStore.agents[0]
)

onMounted(async () => {
  try {
    await agentStore.loadAgents()
    const isRecommended = route.query.recommended === '1'
    const session = await trainingApi.createSession({
      type: type.value,
      recommendation_id: typeof route.query.recommendation_id === 'string' ? route.query.recommendation_id : null,
      recommendation_source: isRecommended && typeof route.query.source === 'string' ? route.query.source : null,
      recommendation_headline: isRecommended && typeof route.query.headline === 'string' ? route.query.headline : null,
      recommendation_task_ids: isRecommended && typeof route.query.tasks === 'string' ? route.query.tasks.split(',').filter(Boolean) : null
    })
    store.setSession(session)
    await speakCurrentTask()
  } catch (err) {
    error.value = toUserMessage(err, '训练会话创建失败')
    avatar.fail('训练会话暂时没有准备好。请刷新后再试一次。')
  }
})

function handleRecorded(blob: Blob) {
  recordedBlob.value = blob
  status.value = '录音已完成，可以上传评分。'
  avatar.encourage('录音已经保存好了。你可以先试听一下，确认后上传评分。')
}

function handleRecordingState(isRecording: boolean) {
  if (isRecording) {
    avatar.stop()
    avatar.listen('我在听。慢慢说，尽量把这一句话说完整。')
  }
}

function handleRecorderError(message: string) {
  error.value = message
  avatar.fail('麦克风好像没有准备好。请检查浏览器权限，或者刷新后再试。')
}

async function submitAttempt() {
  if (!task.value || !recordedBlob.value) return
  loading.value = true
  error.value = ''
  avatar.think('我正在分析这次表达，稍等一下。')
  try {
    const attempt = await attemptsApi.create(task.value.id)
    await attemptsApi.uploadAudio(attempt.id, recordedBlob.value)
    const feedback = await attemptsApi.analyze(attempt.id)
    store.setFeedback(feedback)
    if (currentTaskIndex.value + 1 < tasks.value.length) {
      currentTaskIndex.value += 1
      recordedBlob.value = null
      status.value = '这一项完成了，继续下一项。'
      await speakCurrentTask('这一项完成了，我们继续下一项。', 'next_task')
      return
    }
    await speakWithGeneratedAudio('result_encouragement', '这一组训练完成了。接下来可以看本次反馈。')
    router.push('/training/result')
  } catch (err) {
    error.value = toUserMessage(err, '评分失败')
    avatar.fail('这次分析没有成功。你可以稍后重试，或者重新录一遍。')
  } finally {
    loading.value = false
  }
}

async function speakCurrentTask(prefix = '', sceneName = 'task_demo') {
  if (!task.value) return
  const template = task.value.task_template
  const scene = template.scene_prompt ? `场景是：${template.scene_prompt}。` : ''
  const text = `${prefix}${scene}这次请练习：${template.target_text}`
  await speakWithGeneratedAudio(sceneName, text, task.value.id)
}

async function speakWithGeneratedAudio(scene: string, text: string, sessionTaskId?: string) {
  try {
    const speech = await trainingApi.createAvatarSpeech({
      scene,
      session_id: store.currentSession?.id ?? null,
      session_task_id: sessionTaskId ?? null,
      text
    })
    await avatar.speak(speech.text, speech.audio_url)
  } catch {
    await avatar.speak(text)
  }
}
</script>
