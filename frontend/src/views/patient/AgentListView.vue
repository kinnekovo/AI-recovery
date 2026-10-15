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
      <div v-for="agent in agents" :key="agent.id" class="agent-select" :class="{ 'agent-select-current': isCurrent(agent.id) }">
        <AgentCard :agent="agent" />
        <p v-if="isCurrent(agent.id)" class="current-agent-label">当前陪练</p>
        <VoiceCloneSettings :agent="agent" @updated="updateAgent" />
        <div class="agent-action-row">
          <RouterLink
            v-if="['pending', 'failed'].includes(agent.tencent_avatar_status)"
            class="app-button secondary"
            :to="{ path: '/agent/create', query: { agent: agent.id } }"
          >{{ agent.tencent_avatar_status === 'failed' ? '查看原因并重试' : '继续创建数字人' }}</RouterLink>
          <AppButton
            v-if="['detecting', 'training'].includes(agent.tencent_avatar_status)"
            variant="secondary"
            :loading="loadingAvatarId === agent.id"
            @click="refreshAvatar(agent.id)"
          >查询数字人进度</AppButton>
          <AppButton variant="secondary" :disabled="isCurrent(agent.id) || loadingCurrent" @click="setCurrent(agent.id)">
            {{ isCurrent(agent.id) ? '当前陪练' : '设为当前' }}
          </AppButton>
          <button class="app-button secondary" type="button" :disabled="loadingConsent" @click="revoke(agent.id, 'image')">
            撤回形象授权
          </button>
          <button class="app-button secondary" type="button" :disabled="loadingConsent" @click="revoke(agent.id, 'voice')">
            撤回声音授权
          </button>
          <button class="app-button quiet danger-button" type="button" :disabled="deletingAgentId === agent.id" @click="removeAgent(agent.id, agent.name)">
            {{ deletingAgentId === agent.id ? '正在删除…' : '删除' }}
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
import VoiceCloneSettings from '@/components/agent/VoiceCloneSettings.vue'
import type { Agent } from '@/types/api'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { toUserMessage } from '@/utils/errors'

const store = useAgentStore()
const auth = useAuthStore()
const agents = computed(() => store.agents)
const loadingConsent = ref(false)
const loadingCurrent = ref(false)
const deletingAgentId = ref<string | null>(null)
const loadingAvatarId = ref<string | null>(null)
const message = ref('')
const error = ref('')

onMounted(() => store.loadAgents())

function isCurrent(agentId: string) {
  return auth.me?.patient_profile?.current_agent_id === agentId
}

function updateAgent(updated: Agent) {
  store.agents = store.agents.map((agent) => agent.id === updated.id ? updated : agent)
}

async function setCurrent(agentId: string) {
  loadingCurrent.value = true
  message.value = ''
  error.value = ''
  try {
    await store.setCurrent(agentId)
    await auth.fetchMe()
    message.value = '已设为当前陪练；专属数字人就绪后，训练会自动优先使用它。'
  } catch (err) {
    error.value = toUserMessage(err, '设为当前失败')
  } finally {
    loadingCurrent.value = false
  }
}

async function refreshAvatar(agentId: string) {
  loadingAvatarId.value = agentId
  message.value = ''
  error.value = ''
  try {
    const agent = await store.refreshTencentAvatar(agentId)
    message.value = agent.tencent_avatar_status === 'ready' ? '专属照片数字人已经生成完成。' : '任务仍在处理中，可以稍后再次查询。'
  } catch (err) {
    error.value = toUserMessage(err, '查询照片数字人进度失败')
  } finally {
    loadingAvatarId.value = null
  }
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

async function removeAgent(agentId: string, agentName: string) {
  if (!window.confirm(`确定删除“${agentName}”吗？关联的形象和声音素材将不再在系统中使用。`)) return
  deletingAgentId.value = agentId
  message.value = ''
  error.value = ''
  try {
    await store.remove(agentId)
    await auth.fetchMe()
    message.value = '智能体已删除。'
  } catch (err) {
    error.value = toUserMessage(err, '删除智能体失败')
  } finally {
    deletingAgentId.value = null
  }
}
</script>
