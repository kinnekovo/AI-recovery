<template>
  <section class="training-focus patient-readable" :class="{ paused: session?.status === 'paused' }">
    <header class="training-focus-header">
      <div><p>{{ session?.session_kind === 'extra_practice' ? '额外练习' : '今天的正式训练' }}</p><strong>{{ progressLabel }}</strong></div>
      <div class="focus-header-actions"><RouterLink class="v2-icon-text" to="/training">保存并退出</RouterLink><button v-if="session?.status==='in_progress'||session?.status==='paused'" class="v2-icon-text" :disabled="busy || avatar.isBusy.value" @click="togglePause"><Pause v-if="session?.status==='in_progress'" :size="18"/><Play v-else :size="18"/>{{ session?.status==='in_progress'?'暂停':'继续' }}</button></div>
    </header>

    <div v-if="loading && !session" class="v2-state">正在恢复训练进度…</div>
    <div v-else-if="error && !session" class="v2-state v2-state-error"><strong>训练没有恢复成功</strong><span>{{ error }}</span><button class="v2-button secondary" @click="load">重新加载</button></div>

    <template v-else-if="session && current">
      <div class="session-rail" aria-label="训练进度"><span v-for="item in session.exercises" :key="item.id" :class="item.status"><i></i><small>{{ item.order_index + 1 }}</small></span></div>
      <div class="exercise-stage" :aria-busy="loading">
        <p v-if="loading" class="training-refresh-status" role="status">正在准备下一项练习…</p>
        <div class="training-workspace">
          <AvatarCoachPanel
            class="training-avatar-panel"
            cloud-container-id="v2-repeat-avatar-cloud"
            :snapshot="avatar.snapshot"
            :avatar-url="currentAgent?.avatar_url"
            :avatar-animation-config="currentAgent?.avatar_animation_config"
            :title="current.exercise_type === 'repeat' ? '数字人跟读示范' : '数字人陪伴'"
          >
            <template #actions>
              <button
                v-if="current.exercise_type === 'repeat'"
                class="v2-button secondary repeat-demo-button"
                type="button"
                :disabled="avatar.isBusy.value || recording || loading || session.status !== 'in_progress'"
                @click="speakRepeatTarget"
              >
                <Volume2 :size="19" />{{ avatar.isBusy.value ? '正在示范…' : '听数字人示范' }}
              </button>
            </template>
          </AvatarCoachPanel>

          <div class="training-interaction-column">
            <div class="exercise-brief">
              <p class="v2-section-label">{{ current.exercise_type === 'repeat' ? '跟读练习' : '场景表达' }}</p>
              <h1>{{ current.title }}</h1>
              <p>{{ current.instruction }}</p>
            </div>

            <section v-if="current.exercise_type === 'repeat'" class="practice-surface">
              <div class="target-utterance"><span>请说</span><strong>{{ current.target }}</strong></div>
              <RecorderPanel v-if="session.status==='in_progress' && !avatar.isBusy.value" :key="`${current.id}-${retryKey}`" mode="repeat" :wait-seconds="waitSeconds" @recorded="blob=$event" @recording-state="handleRepeatRecordingState" @recorder-error="error=$event" />
              <p v-else-if="avatar.isBusy.value" class="v2-quiet-copy" aria-live="polite">请先听完数字人示范，再开始录音。</p>
              <p v-else class="v2-quiet-copy">训练已暂停。点击右上角“继续”后再录音。</p>
              <div v-if="feedback" class="instant-feedback" aria-live="polite"><CheckCircle2 :size="26"/><div><strong>这一遍已经完成</strong><p>{{ feedbackText }}</p></div></div>
              <div v-if="statusMessage" class="v2-inline-success" role="status">{{ statusMessage }}</div>
              <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
              <div class="training-actions">
                <button class="v2-button secondary" :disabled="busy||loading||session.status!=='in_progress'" @click="hint"><Lightbulb :size="19"/>给我一点提示</button>
                <button class="v2-button primary" :disabled="!blob || busy || loading || session.status!=='in_progress'" @click="submitRepeat"><Upload :size="19"/>{{ busy?'正在分析…':'提交这一遍' }}</button>
              </div>
            </section>

            <section v-else class="practice-surface">
              <div class="scenario-prompt"><span>场景</span><strong>{{ current.target }}</strong><p>用自己的话表达，不需要照着固定句子说。</p></div>
              <ol v-if="dialogue?.turns?.length" class="v2-dialogue-log"><li v-for="turn in dialogue.turns" :key="turn.turn_index" :class="turn.speaker"><strong>{{ turn.speaker==='agent'?'陪伴助手':'我' }}</strong><p>{{ turn.text }}</p></li></ol>
              <RecorderPanel v-if="dialogue?.status !== 'completed' && session.status==='in_progress'" :key="`${current.id}-${dialogue?.patient_turn_count||0}`" mode="scenario" :wait-seconds="waitSeconds" @recorded="blob=$event" @recording-state="recording=$event" @recorder-error="error=$event"/>
              <div v-if="statusMessage" class="v2-inline-success" role="status">{{ statusMessage }}</div>
              <div v-if="error" class="v2-inline-error" role="alert">{{ error }}</div>
              <div class="training-actions"><button class="v2-button secondary" :disabled="busy||loading||session.status!=='in_progress'" @click="scenarioHint"><Lightbulb :size="19"/>表达提示</button><button v-if="dialogue?.status!=='completed'" class="v2-button primary" :disabled="!blob||busy||loading||session.status!=='in_progress'" @click="submitScenario">{{ busy?'正在听…':'提交这一轮' }}</button><button v-else class="v2-button primary" :disabled="busy||loading" @click="advance">继续</button></div>
            </section>

            <details class="training-more"><summary>我现在有点困难</summary><div><button :disabled="busy||loading||session.status!=='in_progress'" @click="requestHelp">请治疗师关注</button><button :disabled="busy||loading||session.status!=='in_progress'" @click="skip">先跳过这一题</button></div></details>
          </div>
        </div>
      </div>
    </template>

    <section v-else-if="session" class="session-finish-panel"><CheckCircle2 :size="42"/><h1>今天的练习都结束了</h1><p>技术问题和跳过的练习会分开记录，不会算成能力下降。</p><button class="v2-button primary" :disabled="busy" @click="complete">{{ busy?'正在整理…':'查看今天总结' }}</button></section>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CheckCircle2, Lightbulb, Pause, Play, Upload, Volume2 } from 'lucide-vue-next'
import { scenarioDialoguesApi } from '@/api/scenarioDialogues'
import { v2Api, type ExerciseV2, type TrainingSessionV2 } from '@/api/v2'
import { TencentCloudAvatarProvider } from '@/avatar/providers/tencentCloud'
import AvatarCoachPanel from '@/components/avatar/AvatarCoachPanel.vue'
import RecorderPanel from '@/components/training/RecorderPanel.vue'
import { useAvatarRuntime } from '@/composables/useAvatarRuntime'
import { useAgentStore } from '@/stores/agent'
import type { ScenarioDialogue } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const cloudProvider = new TencentCloudAvatarProvider('v2-repeat-avatar-cloud')
const avatar = useAvatarRuntime(cloudProvider)
const session = ref<TrainingSessionV2 | null>(null)
const loading = ref(true)
const busy = ref(false)
const recording = ref(false)
const blob = ref<Blob | null>(null)
const feedback = ref<Record<string, any> | null>(null)
const error = ref('')
const dialogue = ref<ScenarioDialogue | null>(null)
const retryKey = ref(0)
const pendingDialogueTurnId = ref('')
const statusMessage = ref('')
const waitSeconds = Math.max(0, Number(localStorage.getItem('patient_wait_time') || 0))
const current = computed<ExerciseV2 | null>(() => session.value?.current_exercise || null)
const currentAgent = computed(() => {
  const sessionAgent = agentStore.agents.find((agent) => agent.id === session.value?.agent_id)
  return sessionAgent || agentStore.readyAgents[0] || agentStore.agents[0] || null
})
const progressLabel = computed(() => session.value
  ? `${Math.min(session.value.resume_position + 1, session.value.exercises.length)} / ${session.value.exercises.length}`
  : '准备中')
const feedbackText = computed(() => {
  const items = feedback.value?.feedback as Array<{ current_performance: string }> | undefined
  return items?.[0]?.current_performance || '训练事实已经保存，可以继续下一项。'
})

watch([currentAgent, current, loading], async ([agent, exercise, isLoading]) => {
  // The avatar stage is rendered only after the session loader disappears.
  // Waiting for that transition avoids treating a missing DOM container as a
  // Tencent Cloud connection failure.
  if (isLoading) return
  const hasExercise = Boolean(exercise)
  cloudProvider.setAgent(hasExercise ? agent?.id || null : null, hasExercise)
  if (hasExercise) {
    await nextTick()
    await avatar.prepare()
    if (exercise?.exercise_type === 'scenario') avatar.idle('我会陪你完成这个场景练习。')
  }
}, { immediate: true })

async function load() {
  loading.value = true
  error.value = ''
  try {
    const agentPromise = agentStore.agents.length ? Promise.resolve() : agentStore.loadAgents()
    const [loadedSession] = await Promise.all([
      v2Api.session(String(route.params.sessionId)),
      agentPromise,
    ])
    session.value = loadedSession
    await ensureScenario()
  } catch (err) {
    error.value = toUserMessage(err, '请稍后再试。')
  } finally {
    loading.value = false
  }
}

async function ensureScenario() {
  if (current.value?.exercise_type !== 'scenario') return
  dialogue.value = await scenarioDialoguesApi.create(current.value.id)
}

async function speakRepeatTarget() {
  if (!current.value || current.value.exercise_type !== 'repeat' || avatar.isBusy.value || recording.value) return
  error.value = ''
  statusMessage.value = ''
  try {
    await avatar.speak(current.value.target)
  } catch (err) {
    const message = toUserMessage(err, '数字人示范暂时没有播放成功，请稍后重试。')
    error.value = message
    avatar.fail(message)
  }
}

function handleRepeatRecordingState(value: boolean) {
  recording.value = value
  if (value) avatar.listen('我在听，请跟着刚才的示范慢慢说。')
  else if (avatar.snapshot.state === 'listening') avatar.idle('录音完成后，可以提交这一遍。')
}

async function togglePause() {
  if (!session.value || busy.value || avatar.isBusy.value) return
  if (recording.value) {
    error.value = '请先结束当前录音，再暂停训练。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    session.value = await v2Api.sessionCommand(session.value.id, session.value.status === 'paused' ? 'resume' : 'pause')
    statusMessage.value = session.value.status === 'paused' ? '训练已保存并暂停。' : '已继续训练。'
  } catch (err) {
    error.value = toUserMessage(err, '训练状态更新失败。')
  } finally {
    busy.value = false
  }
}

async function hint() {
  if (!session.value || !current.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    session.value = await v2Api.exerciseCommand(session.value.id, current.value.id, 'hint')
    statusMessage.value = `提示等级已调整为 ${session.value.current_exercise?.prompt_level || 1}。先慢慢读清每个词，再连起来说。`
  } catch (err) {
    error.value = toUserMessage(err, '提示暂时不可用。')
  } finally {
    busy.value = false
  }
}

async function requestHelp() {
  if (!session.value || !current.value || busy.value) return
  busy.value = true
  try {
    session.value = await v2Api.exerciseCommand(session.value.id, current.value.id, 'help')
    statusMessage.value = '已告诉治疗师你需要帮助。'
  } catch (err) {
    error.value = toUserMessage(err, '请求没有发送成功。')
  } finally {
    busy.value = false
  }
}

async function skip() {
  if (!session.value || !current.value || busy.value) return
  busy.value = true
  try {
    session.value = await v2Api.exerciseCommand(session.value.id, current.value.id, 'skip')
    blob.value = null
    feedback.value = null
    statusMessage.value = '已跳过这一题。'
    await ensureScenario()
  } catch (err) {
    error.value = toUserMessage(err, '暂时无法跳过这一题。')
  } finally {
    busy.value = false
  }
}

async function submitRepeat() {
  if (!session.value || !current.value || !blob.value || busy.value) return
  busy.value = true
  error.value = ''
  statusMessage.value = ''
  let succeeded = false
  try {
    avatar.think()
    const attempt = await v2Api.createAttempt(current.value.id, current.value.prompt_level)
    await v2Api.uploadAttempt(attempt.id, blob.value)
    const result = await v2Api.analyzeAttempt(attempt.id)
    feedback.value = result.feedback
    avatar.encourage(feedbackText.value)
    succeeded = true
    window.setTimeout(() => { advance().finally(() => { busy.value = false }) }, 900)
  } catch (err) {
    error.value = toUserMessage(err, '录音已保存，但本次分析没有完成。技术失败不会记为能力下降。')
    avatar.fail(error.value)
  } finally {
    if (!succeeded) busy.value = false
  }
}

async function scenarioHint() {
  if (!dialogue.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await scenarioDialoguesApi.hint(dialogue.value.id)
    statusMessage.value = `提示：${result.text}`
  } catch (err) {
    error.value = toUserMessage(err, '表达提示暂时不可用。')
  } finally {
    busy.value = false
  }
}

async function submitScenario() {
  if (!dialogue.value || !blob.value) return
  busy.value = true
  try {
    pendingDialogueTurnId.value ||= crypto.randomUUID()
    dialogue.value = await scenarioDialoguesApi.uploadTurn(dialogue.value.id, blob.value, pendingDialogueTurnId.value)
    pendingDialogueTurnId.value = ''
    blob.value = null
    if (dialogue.value.status === 'completed') await advance()
  } catch (err) {
    error.value = toUserMessage(err, '这一轮没有识别成功，请重新录音。')
  } finally {
    busy.value = false
  }
}

async function advance() {
  avatar.stop()
  feedback.value = null
  blob.value = null
  statusMessage.value = ''
  retryKey.value += 1
  await load()
}

async function complete() {
  if (!session.value) return
  busy.value = true
  try {
    session.value = await v2Api.sessionCommand(session.value.id, 'complete')
    await router.push(`/training/session/${session.value.id}/summary`)
  } catch (err) {
    error.value = toUserMessage(err, '还有练习未结束，请返回继续完成。')
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>
