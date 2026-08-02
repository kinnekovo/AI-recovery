import { defineStore } from 'pinia'
import type { ScoreResult, TrainingSession } from '@/types/api'

export const useTrainingStore = defineStore('training', {
  state: () => ({
    currentSession: null as TrainingSession | null,
    latestScore: null as ScoreResult | null
  }),
  actions: {
    setSession(session: TrainingSession) {
      this.currentSession = session
    },
    setScore(score: ScoreResult) {
      this.latestScore = score
    }
  }
})
