<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">进入训练</span>
      <h1>{{ isTodayRecommendationCompleted ? '今日建议任务已完成' : '今天练一组从易到难的小任务' }}</h1>
      <p>
        {{
          isTodayRecommendationCompleted
            ? '今天的建议任务组已经完成，接下来可以自主安排训练，也可以休息恢复。'
            : '系统会根据你的能力画像安排热身、主练和挑战，完成一组比只练一项更稳定。'
        }}
      </p>
    </div>
    <AvatarCoachPanel immersive :snapshot="avatar.snapshot" :avatar-url="currentAgent?.avatar_url" :avatar-animation-config="currentAgent?.avatar_animation_config" title="今天由数字人陪你练">
      <template #actions>
        <button class="app-button secondary avatar-action-button" type="button" :disabled="avatar.isBusy.value" @click="playCoachIntro">
          {{ avatar.isBusy.value ? '正在说明' : '听数字人说明' }}
        </button>
      </template>
    </AvatarCoachPanel>
    <section v-if="recommendation" class="recommendation-panel training-group-panel" :class="{ completed: isTodayRecommendationCompleted }">
      <div class="recommendation-copy">
        <span class="recommendation-label">
          {{ isTodayRecommendationCompleted ? '今日已完成' : recommendation.source === 'therapist' ? '治疗师建议' : '系统建议' }}
        </span>
        <h2>{{ isTodayRecommendationCompleted ? '可自主安排训练' : recommendation.headline }}</h2>
        <p>
          {{
            isTodayRecommendationCompleted
              ? '建议任务已经完成。下面的自选训练可以按体力和心情选择，不需要重复完成同一组推荐。'
              : recommendation.reason
          }}
        </p>
        <small v-if="recommendation.therapist_notes && !isTodayRecommendationCompleted">治疗师备注：{{ recommendation.therapist_notes }}</small>
        <small v-if="recommendation.adaptation_note && !isTodayRecommendationCompleted">{{ recommendation.adaptation_note }}</small>
        <small v-if="recommendation.reminder && !isTodayRecommendationCompleted">{{ recommendation.reminder }}</small>
      </div>
      <div v-if="!isTodayRecommendationCompleted" class="recommendation-action">
        <span>{{ recommendation.suggested_minutes }} 分钟</span>
        <RouterLink class="primary-link" :to="recommendedTrainingLink(recommendation)">按建议开始</RouterLink>
      </div>
      <div v-if="!isTodayRecommendationCompleted" class="focus-strip">
        <span v-for="point in recommendation.focus_points" :key="point">{{ point }}</span>
      </div>
      <div v-if="recommendedTasks.length" class="recommended-task-sequence">
        <article v-for="(task, index) in recommendedTasks" :key="task.id" class="recommended-task-step">
          <div class="step-index">{{ index + 1 }}</div>
          <div>
            <span>{{ stepLabel(index) }} · {{ trainingTypeLabel(task.task_type) }} · {{ task.content_level }}/{{ task.autonomy_level }}</span>
            <strong>{{ task.title }}</strong>
            <p>{{ taskDisplayText(task) }}</p>
          </div>
        </article>
      </div>
    </section>
    <p v-if="error" class="error-text">{{ error }}</p>
    <div class="training-choice manual-choice">
      <RouterLink class="choice-panel" :class="{ recommended: recommendation?.recommended_type === 'repeat' }" to="/training/repeat">
        <span class="choice-badge">自选</span>
        <strong>跟读训练</strong>
        <p>系统展示目标句子，你录音跟读。适合先把一句话说完整、说清楚。</p>
      </RouterLink>
      <RouterLink
        class="choice-panel"
        :class="{ recommended: recommendation?.recommended_type === 'scenario' }"
        to="/training/scenario"
      >
        <span class="choice-badge">自选</span>
        <strong>场景表达</strong>
        <p>围绕生活场景自由表达。适合练习把想法组织起来，说出自己的需求。</p>
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AvatarCoachPanel from '@/components/avatar/AvatarCoachPanel.vue'
import { trainingApi } from '@/api/training'
import { useAvatarRuntime } from '@/composables/useAvatarRuntime'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { toUserMessage } from '@/utils/errors'
import type { TodayTraining, TrainingRecommendation } from '@/types/api'

const agentStore = useAgentStore()
const auth = useAuthStore()
const today = ref<TodayTraining | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const error = ref('')
const avatar = useAvatarRuntime()
const recommendedTasks = computed(() => recommendation.value?.task_sequence?.length ? recommendation.value.task_sequence : [])
const isTodayRecommendationCompleted = computed(() => Boolean(today.value?.recommended_completed))
const currentAgent = computed(() =>
  agentStore.agents.find((agent) => agent.id === auth.me?.patient_profile?.current_agent_id) || agentStore.agents[0]
)

onMounted(async () => {
  await agentStore.loadAgents()
  const [todayResult, recommendationResult] = await Promise.allSettled([trainingApi.today(), trainingApi.recommendation()])
  if (todayResult.status === 'fulfilled') {
    today.value = todayResult.value
  }
  if (recommendationResult.status === 'fulfilled') {
    recommendation.value = recommendationResult.value
  } else {
    error.value = recommendationResult.reason instanceof Error ? recommendationResult.reason.message : '暂时无法读取训练建议，可以先手动选择训练。'
  }
  avatar.encourage(coachIntroText())
})

function recommendedTrainingLink(item: TrainingRecommendation) {
  return {
    path: `/training/${item.recommended_type}`,
    query: {
      recommended: '1',
      source: item.source,
      ...(item.id ? { recommendation_id: item.id } : {}),
      headline: item.headline,
      tasks: recommendedTasks.value.map((task) => task.id).join(',')
    }
  }
}

function stepLabel(index: number) {
  return ['热身', '主练', '挑战'][index] || `第 ${index + 1} 项`
}

function trainingTypeLabel(type: string) {
  return type === 'scenario' ? '场景表达' : '跟读'
}

function taskDisplayText(task: { task_type: string; target_text: string; scoring_config?: Record<string, unknown> }) {
  if (task.task_type === 'scenario') {
    return String(task.scoring_config?.display_prompt || '围绕生活场景自由表达，说清自己的需要。')
  }
  return task.target_text
}

async function playCoachIntro() {
  await speakWithGeneratedAudio('training_intro', coachIntroText())
}

function coachIntroText() {
  if (isTodayRecommendationCompleted.value) {
    return '今天的建议任务已经完成了。接下来你可以自己选择想练的内容，也可以休息一下。'
  }
  const tasksCount = recommendedTasks.value.length
  if (recommendation.value && tasksCount > 1) {
    return `今天我们练 ${tasksCount} 个小任务，从简单到稍难。我会先陪你看清楚要说什么，再等你录音。`
  }
  if (recommendation.value) {
    return `今天建议先练${recommendation.value.headline}。不用着急，我们一次只完成一小步。`
  }
  return '暂时没有读取到建议任务，你可以先选择跟读训练或场景表达，我会陪你完成。'
}

async function speakWithGeneratedAudio(scene: string, text: string) {
  error.value = ''
  try {
    const speech = await trainingApi.createAvatarSpeech({ scene, text })
    await avatar.speak(speech.text, speech.audio_url, speech.video_task?.id)
  } catch (err) {
    const message = toUserMessage(err, '数字人语音未能生成。')
    error.value = message
    avatar.fail(`${message} 未创建动态形象任务，请检查后重试。`)
  }
}
</script>
