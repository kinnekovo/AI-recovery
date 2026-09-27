import { http, request } from './http'
import type { ScenarioDialogue, ScenarioDialogueEvaluation } from '@/types/api'

export interface ScenarioDialogueTrends {
  training: { dialogue_count: number; independent_goal_achievement_rate: number | null; median_information_score: number | null; effective_response_rate: number | null; average_prompt_level: number | null; observed_repair_success_rate: number | null }
  generalization_probe: { dialogue_count: number; independent_goal_achievement_rate: number | null; median_information_score: number | null; effective_response_rate: number | null; average_prompt_level: number | null; observed_repair_success_rate: number | null }
}

const audioExtensionByMimeType: Record<string, string> = {
  'audio/ogg': 'ogg',
  'audio/ogg;codecs=opus': 'ogg',
  'audio/webm': 'webm',
  'audio/webm;codecs=opus': 'webm'
}

// A scenario turn may include browser upload, Tencent ASR, semantic extraction,
// and a contextual role reply. Keep the normal API timeout short, but allow this
// deliberately multi-provider request enough time to finish.
const SCENARIO_TURN_TIMEOUT_MS = 60_000

export const scenarioDialoguesApi = {
  trends() {
    return request<ScenarioDialogueTrends>(http.get('/scenario-dialogues/trends'))
  },
  create(sessionTaskId: string) {
    return request<ScenarioDialogue>(http.post('/scenario-dialogues', { session_task_id: sessionTaskId }))
  },
  get(dialogueId: string) {
    return request<ScenarioDialogue>(http.get(`/scenario-dialogues/${dialogueId}`))
  },
  evaluation(dialogueId: string) {
    return request<ScenarioDialogueEvaluation>(http.get(`/scenario-dialogues/${dialogueId}/evaluation`))
  },
  hint(dialogueId: string) {
    return request<{ level: number; text: string }>(http.post(`/scenario-dialogues/${dialogueId}/hint`))
  },
  finish(dialogueId: string) {
    return request<ScenarioDialogue>(http.post(`/scenario-dialogues/${dialogueId}/finish`))
  },
  uploadTurn(dialogueId: string, audio: Blob, clientTurnId: string) {
    const form = new FormData()
    form.append('audio_file', audio, `scenario-turn.${audioExtensionByMimeType[audio.type] ?? 'webm'}`)
    form.append('client_turn_id', clientTurnId)
    return request<ScenarioDialogue>(http.post(`/scenario-dialogues/${dialogueId}/turns/audio`, form, { timeout: SCENARIO_TURN_TIMEOUT_MS }))
  }
}
