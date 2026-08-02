import { defineStore } from 'pinia'
import { authApi, type MeResult } from '@/api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || '',
    me: null as MeResult | null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token)
  },
  actions: {
    async login(username: string, password: string) {
      const result = await authApi.login(username, password)
      this.token = result.access_token
      localStorage.setItem('access_token', result.access_token)
      await this.fetchMe()
    },
    async register(username: string, password: string) {
      await authApi.register(username, password)
      await this.login(username, password)
    },
    async fetchMe() {
      this.me = await authApi.me()
    },
    logout() {
      this.token = ''
      this.me = null
      localStorage.removeItem('access_token')
    }
  }
})
