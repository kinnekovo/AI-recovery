<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">{{ groupLabel }}</span>
      <h1>{{ task?.task_template.title || '准备训练' }}</h1>
      <p>{{ task?.task_template.instruction || '正在生成训练会话。' }}</p>
    </div>
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
      <RecorderPanel @recorded="handleRecorded" />
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
import AppButton from '@/components/common/AppButton.vue'
import RecorderPanel from '@/components/training/RecorderPanel.vue'
import { attemptsApi } from '@/api/attempts'
import { trainingApi } from '@/api/training'
import { useTrainingStore } from '@/stores/training'

const route = useRoute()
const router = useRouter()
const store = useTrainingStore()
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

onMounted(async () => {
  const isRecommended = route.query.recommended === '1'
  const session = await trainingApi.createSession({
    type: type.value,
    recommendation_id: typeof route.query.recommendation_id === 'string' ? route.query.recommendation_id : null,
    recommendation_source: isRecommended && typeof route.query.source === 'string' ? route.query.source : null,
    recommendation_headline: isRecommended && typeof route.query.headline === 'string' ? route.query.headline : null,
    recommendation_task_ids: isRecommended && typeof route.query.tasks === 'string' ? route.query.tasks.split(',').filter(Boolean) : null
  })
  store.setSession(session)
})

function handleRecorded(blob: Blob) {
  recordedBlob.value = blob
  status.value = '录音已完成，可以上传评分。'
}

async function submitAttempt() {
  if (!task.value || !recordedBlob.value) return
  loading.value = true
  error.value = ''
  try {
    const attempt = await attemptsApi.create(task.value.id)
    await attemptsApi.uploadAudio(attempt.id, recordedBlob.value)
    const feedback = await attemptsApi.analyze(attempt.id)
    store.setFeedback(feedback)
    if (currentTaskIndex.value + 1 < tasks.value.length) {
      currentTaskIndex.value += 1
      recordedBlob.value = null
      status.value = '这一项完成了，继续下一项。'
      return
    }
    router.push('/training/result')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '评分失败'
  } finally {
    loading.value = false
  }
}
</script>
