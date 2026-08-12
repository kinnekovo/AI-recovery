<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">今日闭环</span>
      <h1>准备开始一次轻量训练</h1>
      <p>先选择或创建陪伴智能体，再完成一题跟读或场景表达。</p>
    </div>
    <section class="home-grid">
      <div class="primary-panel">
        <h2>当前进度</h2>
        <p v-if="today">今日计划包含 {{ today.items_count }} 项任务，状态：{{ today.status }}</p>
        <p v-else>正在获取今日训练。</p>
        <div v-if="recommendation" class="home-recommendation">
          <span>{{ recommendation.source === 'therapist' ? '治疗师建议' : '系统建议' }}</span>
          <strong>{{ recommendation.headline }}</strong>
          <p>{{ recommendation.reason }}</p>
          <small v-if="recommendation.therapist_notes">治疗师备注：{{ recommendation.therapist_notes }}</small>
        </div>
        <p v-if="recommendationError" class="error-text">{{ recommendationError }}</p>
        <RouterLink class="primary-link" :to="recommendation ? `/training/${recommendation.recommended_type}` : '/training'">
          按建议开始
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
import type { TrainingRecommendation } from '@/types/api'

const agentStore = useAgentStore()
const auth = useAuthStore()
const today = ref<{ plan_id: string; title: string; status: string; items_count: number } | null>(null)
const recommendation = ref<TrainingRecommendation | null>(null)
const recommendationError = ref('')

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
    recommendationError.value = '暂时无法读取训练建议，可以进入训练页手动选择。'
  }
})
</script>
