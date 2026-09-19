<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">{{ groupLabel }}</span>
      <h1>{{ task?.task_template.title || '准备训练' }}</h1>
      <p>{{ task?.task_template.instruction || '正在生成训练会话。' }}</p>
    </div>
    <AvatarCoachPanel v-if="task" cloud-container-id="training-session-avatar-cloud" :snapshot="avatar.snapshot" :avatar-url="currentAgent?.avatar_url" :avatar-animation-config="currentAgent?.avatar_animation_config" title="数字人陪练中" compact>
      <template #actions>
        <button class="app-button secondary avatar-action-button" type="button" :disabled="avatar.isBusy.value" @click="() => speakCurrentTask()">
          {{ avatar.isBusy.value ? '正在示范' : '听数字人示范' }}
        </button>
      </template>
    </AvatarCoachPanel>
    <section v-if="task" class="task-panel">
      <template v-if="isScenario">
        <div class="task-target scenario-dialogue-target">
          <span>{{ task.task_template.content_level }} · 自由对话</span>
          <p v-if="task.task_template.scene_prompt">场景：{{ task.task_template.scene_prompt }}</p>
          <h2>{{ dialogue?.communication_goal || '正在准备对话场景' }}</h2>
          <p class="free-expression-note">像真实交流一样回答即可；数字人会根据你刚才说的内容继续提问。</p>
        </div>
        <ol v-if="dialogue" class="scenario-dialogue-log" aria-label="本次对话记录" aria-live="polite">
          <li v-for="turn in dialogue.turns" :key="turn.turn_index" :class="['dialogue-turn', turn.speaker]">
            <strong>{{ turn.speaker === 'agent' ? '数字人' : '我' }}</strong>
            <p>{{ turn.text }}</p>
          </li>
        </ol>
        <p v-if="dialogue?.status === 'completed'" class="success-text">这一段对话结束了。完整功能评分将在本次训练报告中汇总。</p>
        <div v-else class="patient-trial-hints" aria-label="本轮对话提示">
          <span>听完再说</span><span>用自己的话</span><span>需要时可求提示</span>
        </div>
        <RecorderPanel
          v-if="dialogue?.status === 'active'"
          :key="`${task.id}-${dialogue.id}-${dialogue.patient_turn_count}`"
          mode="scenario"
          @recorded="handleRecorded"
          @recording-state="handleRecordingState"
          @recorder-error="handleRecorderError"
        />
        <div v-if="dialogue?.status === 'active'" class="scenario-dialogue-actions">
          <button class="text-action" type="button" :disabled="loading" @click="requestDialogueHint">给我一个表达提示</button>
          <button class="text-action" type="button" :disabled="loading" @click="finishDialogue">先结束本次对话</button>
          <AppButton variant="primary" :disabled="!recordedBlob" :loading="loading" @click="submitDialogueTurn">提交这一轮表达</AppButton>
        </div>
        <AppButton v-else variant="primary" @click="router.push(`/training/scenario/result/${dialogue?.id}`)">查看本次训练小结</AppButton>
      </template>
      <template v-else>
      <div v-if="tasks.length > 1" class="session-step-strip">
        <span v-for="(item, index) in tasks" :key="item.id" :class="{ active: index === currentTaskIndex, done: index < currentTaskIndex }">
          {{ index + 1 }}
        </span>
      </div>
      <div class="task-target">
        <span>{{ task.task_template.content_level }} · {{ task.task_template.autonomy_level }}</span>
        <h2>{{ task.task_template.target_text }}</h2>
        <p>请听数字人示范后，再完整跟读。</p>
      </div>
      <div class="patient-trial-hints" aria-label="训练前确认">
        <span>安静一点</span>
        <span>看清句子</span>
        <span>说完再停</span>
      </div>
      <RecorderPanel
        :key="task.id"
        mode="repeat"
        @recorded="handleRecorded"
        @recording-state="handleRecordingState"
        @recorder-error="handleRecorderError"
      />
      <p v-if="status" class="success-text">{{ status }}</p>
      <p v-if="error" class="error-text">{{ error }}</p>
      <AppButton variant="primary" :disabled="!recordedBlob" :loading="loading" @click="submitAttempt">
        {{ currentTaskIndex + 1 < tasks.length ? '上传并进入下一项' : '上传录音并生成反馈' }}
      </AppButton>
      </template>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AvatarCoachPanel from '@/components/avatar/AvatarCoachPanel.vue'
import AppButton from '@/components/common/AppButton.vue'
import RecorderPanel from '@/components/training/RecorderPanel.vue'
import { attemptsApi } from '@/api/attempts'
import { scenarioDialoguesApi } from '@/api/scenarioDialogues'
import { trainingApi } from '@/api/training'
import type { ScenarioDialogue } from '@/types/api'
import { useAvatarRuntime } from '@/composables/useAvatarRuntime'
import { AliyunCloudAvatarProvider } from '@/avatar/providers/aliyunCloud'
import { useAgentStore } from '@/stores/agent'
import { useTrainingStore } from '@/stores/training'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const store = useTrainingStore()
const agentStore = useAgentStore()
const type = computed(() => route.params.type as 'repeat' | 'scenario')
const tasks = computed(() => store.currentSession?.session_tasks || [])
const currentTaskIndex = ref(0)
const task = computed(() => tasks.value[currentTaskIndex.value])
const groupLabel = computed(() => {
  if (route.query.mode === 'generalization_probe') return '新场景小测'
  if (tasks.value.length > 1) return `今日任务组 ${currentTaskIndex.value + 1}/${tasks.value.length}`
  return type.value === 'repeat' ? '跟读训练' : '场景表达'
})
const recordedBlob = ref<Blob | null>(null)
const loading = ref(false)
const status = ref('')
const error = ref('')
const dialogue = ref<ScenarioDialogue | null>(null)
const pendingDialogueTurnId = ref('')
const promptLevel = ref(0)
const requestedHelp = ref(false)
const currentAgent = computed(() =>
  agentStore.agents.find((agent) => agent.id === store.currentSession?.agent_id) || agentStore.agents[0]
)
const cloudProvider = new AliyunCloudAvatarProvider('training-session-avatar-cloud')
const avatar = useAvatarRuntime(cloudProvider)

watch(currentAgent, (agent) => cloudProvider.setAgent(agent?.id || null), { immediate: true })
const isScenario = computed(() => task.value?.task_template.task_type === 'scenario')
const sceneConfig = computed(() => (task.value?.task_template.scoring_config || {}) as Record<string, unknown>)
const isGeneralizationProbe = computed(() => sceneConfig.value.evaluation_role === 'generalization_probe')
const sceneDisplayPrompt = computed(() => String(sceneConfig.value.display_prompt || task.value?.task_template.instruction || '请围绕这个场景自由表达。'))
const sceneClues = computed(() => {
  const units = sceneConfig.value.required_information_units
  if (!Array.isArray(units)) return []
  return units
    .map((unit) => (unit && typeof unit === 'object' && 'label' in unit ? String(unit.label) : ''))
    .filter(Boolean)
    .slice(0, 3)
})
const sceneHints = computed(() => (Array.isArray(sceneConfig.value.prompt_hints) ? sceneConfig.value.prompt_hints.map(String) : []))
const activeHint = computed(() => (promptLevel.value ? sceneHints.value[promptLevel.value - 1] || '' : ''))

onMounted(async () => {
  try {
    await agentStore.loadAgents()
    const isRecommended = route.query.recommended === '1'
    const session = await trainingApi.createSession({
      type: type.value,
      scenario_mode: route.query.mode === 'generalization_probe' ? 'generalization_probe' : 'training',
      recommendation_id: typeof route.query.recommendation_id === 'string' ? route.query.recommendation_id : null,
      recommendation_source: isRecommended && typeof route.query.source === 'string' ? route.query.source : null,
      recommendation_headline: isRecommended && typeof route.query.headline === 'string' ? route.query.headline : null,
      recommendation_task_ids: isRecommended && typeof route.query.tasks === 'string' ? route.query.tasks.split(',').filter(Boolean) : null
    })
    store.setSession(session)
    if (task.value?.task_template.task_type === 'scenario') {
      dialogue.value = await scenarioDialoguesApi.create(task.value.id)
    }
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
    const attempt = await attemptsApi.create(task.value.id, {
      prompt_level: promptLevel.value,
      requested_help: requestedHelp.value
    })
    await attemptsApi.uploadAudio(attempt.id, recordedBlob.value)
    const feedback = await attemptsApi.analyze(attempt.id)
    store.setFeedback(feedback)
    if (currentTaskIndex.value + 1 < tasks.value.length) {
      currentTaskIndex.value += 1
      recordedBlob.value = null
      promptLevel.value = 0
      requestedHelp.value = false
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
  const text = template.task_type === 'scenario'
    ? `${prefix}${scene}${sceneDisplayPrompt.value}。${isGeneralizationProbe.value ? '这是一个新场景小测，用自己的话说清楚就可以。' : '你可以用自己的话说，不用重复示范句。'}`
    : `${prefix}${scene}这次请练习：${template.target_text}`
  await speakWithGeneratedAudio(sceneName, text, task.value.id)
}

async function submitDialogueTurn() {
  if (!dialogue.value || !recordedBlob.value) return
  loading.value = true
  error.value = ''
  avatar.think('我正在听这一轮表达。')
  try {
    pendingDialogueTurnId.value ||= crypto.randomUUID()
    dialogue.value = await scenarioDialoguesApi.uploadTurn(dialogue.value.id, recordedBlob.value, pendingDialogueTurnId.value)
    pendingDialogueTurnId.value = ''
    recordedBlob.value = null
    const lastAgentTurn = [...dialogue.value.turns].reverse().find((turn) => turn.speaker === 'agent')
    if (lastAgentTurn) await speakWithGeneratedAudio('scenario_follow_up', lastAgentTurn.text, task.value?.id)
    if (dialogue.value.status === 'completed') {
      status.value = '对话已完成，可以查看本次训练小结。'
      avatar.encourage('这一段对话完成了。接下来我们会根据完整对话来整理反馈。')
    } else {
      status.value = '数字人已根据你的表达继续追问。请回答下一轮。'
    }
  } catch (err) {
    error.value = toUserMessage(err, '本轮提交失败')
    avatar.fail('这一轮没有识别成功。请重新录一遍，或稍后再试。')
  } finally {
    loading.value = false
  }
}

async function requestDialogueHint() {
  if (!dialogue.value) return
  try {
    const hint = await scenarioDialoguesApi.hint(dialogue.value.id)
    status.value = `提示：${hint.text}`
    await avatar.speak(`提示：${hint.text}`)
  } catch (err) {
    error.value = toUserMessage(err, '暂时没有更多提示')
  }
}

async function finishDialogue() {
  if (!dialogue.value) return
  loading.value = true
  try {
    dialogue.value = await scenarioDialoguesApi.finish(dialogue.value.id)
    status.value = '已结束本次对话，已完成的表达会保留在训练记录中。'
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法结束本次对话')
  } finally {
    loading.value = false
  }
}

function showHint() {
  if (!sceneHints.value.length || promptLevel.value >= sceneHints.value.length) return
  promptLevel.value += 1
  requestedHelp.value = true
  avatar.encourage(`提示来了：${activeHint.value}`)
}

async function speakWithGeneratedAudio(scene: string, text: string, sessionTaskId?: string) {
  error.value = ''
  try {
    const speech = await trainingApi.createAvatarSpeech({
      scene,
      session_id: store.currentSession?.id ?? null,
      session_task_id: sessionTaskId ?? null,
      text
    })
    await avatar.speak(speech.text, speech.audio_url)
  } catch (err) {
    const message = toUserMessage(err, '数字人语音未能生成。')
    error.value = message
    avatar.fail(`${message} 当前已保留本地形象与语音回退。`)
  }
}
</script>
