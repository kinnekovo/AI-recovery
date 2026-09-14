import { defineStore } from 'pinia'
import { agentsApi } from '@/api/agents'
import type { Agent } from '@/types/api'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    agents: [] as Agent[],
    audioUrl: ''
  }),
  getters: {
    readyAgents: (state) => state.agents.filter((agent) => agent.generation_status === 'ready')
  },
  actions: {
    async loadAgents() {
      this.agents = await agentsApi.list()
    },
    async setCurrent(agentId: string) {
      await agentsApi.setCurrent(agentId)
      await this.loadAgents()
    },
    async revokeConsent(agentId: string, consentType: 'image' | 'voice') {
      await agentsApi.revokeConsent(agentId, consentType)
      await this.loadAgents()
    },
    async remove(agentId: string) {
      await agentsApi.remove(agentId)
      await this.loadAgents()
    }
  }
})
