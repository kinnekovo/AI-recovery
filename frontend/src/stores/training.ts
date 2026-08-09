import { defineStore } from 'pinia'
import type { TrainingFeedbackResult, TrainingSession } from '@/types/api'

export const useTrainingStore = defineStore('training', {
  state: () => ({
    currentSession: null as TrainingSession | null,
    latestFeedback: null as TrainingFeedbackResult | null
  }),
  actions: {
    setSession(session: TrainingSession) {
      this.currentSession = session
    },
    setFeedback(feedback: TrainingFeedbackResult) {
      this.latestFeedback = feedback
    }
  }
})
