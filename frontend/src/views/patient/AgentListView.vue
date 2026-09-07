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
        <div class="agent-action-row">
          <AppButton variant="secondary" @click="setCurrent(agent.id)">设为当前</AppButton>
          <button class="app-button secondary" type="button" :disabled="loadingConsent" @click="revoke(agent.id, 'image')">
            撤回形象授权
          </button>
          <button class="app-button secondary" type="button" :disabled="loadingConsent" @click="revoke(agent.id, 'voice')">
            撤回声音授权
          </button>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <p>还没有智能体。</p>
      <RouterLink to="/agent/create">创建第一个</RouterLink>
    </div>
    <p v-if="message" class="success-text">{{ message }}</p>
    <p v-if="error" class="error-text">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppButton from '@/components/common/AppButton.vue'
import AgentCard from '@/components/agent/AgentCard.vue'
import { useAgentStore } from '@/stores/agent'
import { toUserMessage } from '@/utils/errors'

const store = useAgentStore()
const agents = computed(() => store.agents)
const loadingConsent = ref(false)
const message = ref('')
const error = ref('')

onMounted(() => store.loadAgents())

function setCurrent(agentId: string) {
  store.setCurrent(agentId)
}

async function revoke(agentId: string, consentType: 'image' | 'voice') {
  loadingConsent.value = true
  message.value = ''
  error.value = ''
  try {
    await store.revokeConsent(agentId, consentType)
    message.value = consentType === 'voice' ? '已撤回声音授权，后续不会继续使用该声音生成新内容。' : '已撤回形象授权，后续不能继续更新该形象素材。'
  } catch (err) {
    error.value = toUserMessage(err, '授权撤回失败')
  } finally {
    loadingConsent.value = false
  }
}
</script>
