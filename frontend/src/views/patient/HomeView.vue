<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">今日闭环</span>
      <h1>{{ isTodayRecommendationCompleted ? '今日建议任务已完成' : '准备开始今天的任务组' }}</h1>
      <p>
        {{
          isTodayRecommendationCompleted
            ? '今天的建议训练已经完成，接下来可以休息，也可以自主安排轻量练习。'
            : '先选择或创建陪伴智能体，再完成一组从易到难的小任务。'
        }}
      </p>
    </div>
    <section class="home-grid">
      <div class="primary-panel">
        <h2>当前进度</h2>
        <p v-if="today">
          {{
            isTodayRecommendationCompleted
              ? `今日建议任务已完成，已完成 ${today.completed_recommended_sessions} 组推荐训练。`
              : `今日计划包含 ${today.items_count} 项任务，状态：${today.status}`
          }}
        </p>
        <p v-else>正在获取今日训练。</p>
        <div v-if="recommendation" class="home-recommendation" :class="{ completed: isTodayRecommendationCompleted }">
          <span>{{ isTodayRecommendationCompleted ? '今日已完成' : recommendation.source === 'therapist' ? '治疗师建议' : '系统建议' }}</span>
          <strong>{{ isTodayRecommendationCompleted ? '可自主安排训练' : recommendation.headline }}</strong>
          <p>{{ isTodayRecommendationCompleted ? '今天的建议任务组已经完成。后续练习可以按自己的状态选择，感觉疲劳时也可以到此为止。' : recommendation.reason }}</p>
          <small v-if="recommendation.task_sequence?.length && !isTodayRecommendationCompleted">今日建议 {{ recommendation.task_sequence.length }} 项：{{ recommendation.task_sequence.map((task) => task.title).join('、') }}</small>
          <small v-if="recommendation.therapist_notes && !isTodayRecommendationCompleted">治疗师备注：{{ recommendation.therapist_notes }}</small>
        </div>
        <p v-if="recommendationError" class="error-text">{{ recommendationError }}</p>
        <RouterLink class="primary-link" :to="isTodayRecommendationCompleted || !recommendation ? '/training' : recommendedTrainingLink(recommendation)">
          {{ isTodayRecommendationCompleted ? '自主安排训练' : '按建议开始' }}
        </RouterLink>
      </div>
      <div class="side-panel">
        <h2>陪伴智能体</h2>
        <AgentCard v-if="currentAgent" :agent="currentAgent" />
        <div v-else class="empty-state">
          <p>还没有可用智能体。</p>
          <RouterLink to="/agent/create">创建智能体</RouterLink>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AgentCard from '@/components/agent/AgentCard.vue'
import { trainingApi } from '@/api/training'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import type { TodayTraining, TrainingRecommendation } from '@/types/api'

const agentStore = useAgentStore()
const auth = useAuthStore()
const today = ref<TodayTraining | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const recommendationError = ref('')

const currentAgent = computed(() =>
  agentStore.agents.find((agent) => agent.id === auth.me?.patient_profile?.current_agent_id) || agentStore.agents[0]
)
const isTodayRecommendationCompleted = computed(() => Boolean(today.value?.recommended_completed))

onMounted(async () => {
  await agentStore.loadAgents()
  const [todayResult, recommendationResult] = await Promise.allSettled([trainingApi.today(), trainingApi.recommendation()])
  if (todayResult.status === 'fulfilled') {
    today.value = todayResult.value
  }
  if (recommendationResult.status === 'fulfilled') {
    recommendation.value = recommendationResult.value
  } else {
    recommendationError.value = '暂时无法读取训练建议，可以进入训练页手动选择。'
  }
})

function recommendedTrainingLink(item: TrainingRecommendation) {
  return {
    path: `/training/${item.recommended_type}`,
    query: {
      recommended: '1',
      source: item.source,
      ...(item.id ? { recommendation_id: item.id } : {}),
      headline: item.headline,
      tasks: (item.task_sequence || []).map((task) => task.id).join(',')
    }
  }
}
</script>
