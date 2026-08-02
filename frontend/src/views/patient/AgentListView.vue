<template>
  <section class="page-stack">
    <div class="page-heading split">
      <div>
        <span class="kicker">我的智能体</span>
        <h1>选择今天陪你训练的人</h1>
      </div>
      <RouterLink class="secondary-link" to="/agent/create">新建</RouterLink>
    </div>
    <div v-if="agents.length" class="agent-grid">
      <div v-for="agent in agents" :key="agent.id" class="agent-select">
        <AgentCard :agent="agent" />
        <AppButton variant="secondary" @click="setCurrent(agent.id)">设为当前</AppButton>
      </div>
    </div>
    <div v-else class="empty-state">
      <p>还没有智能体。</p>
      <RouterLink to="/agent/create">创建第一个</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppButton from '@/components/common/AppButton.vue'
import AgentCard from '@/components/agent/AgentCard.vue'
import { useAgentStore } from '@/stores/agent'

const store = useAgentStore()
const agents = computed(() => store.agents)

onMounted(() => store.loadAgents())

function setCurrent(agentId: string) {
  store.setCurrent(agentId)
}
</script>
