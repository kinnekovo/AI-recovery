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
        <RouterLink class="primary-link" to="/training">开始训练</RouterLink>
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

const agentStore = useAgentStore()
const auth = useAuthStore()
const today = ref<{ plan_id: string; title: string; status: string; items_count: number } | null>(null)

const currentAgent = computed(() =>
  agentStore.agents.find((agent) => agent.id === auth.me?.patient_profile?.current_agent_id) || agentStore.agents[0]
)

onMounted(async () => {
  await agentStore.loadAgents()
  today.value = await trainingApi.today()
})
</script>
