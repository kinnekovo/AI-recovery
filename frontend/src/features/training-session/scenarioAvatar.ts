import type { ScenarioDialogue, ScenarioDialogueTurn } from '@/types/api'

const STORAGE_PREFIX = 'scenario-avatar-spoken'

export function latestAgentTurn(dialogue: ScenarioDialogue | null): ScenarioDialogueTurn | null {
  if (!dialogue) return null
  return [...dialogue.turns].reverse().find((turn) => turn.speaker === 'agent') || null
}

export function scenarioTurnToken(dialogueId: string, turnIndex: number) {
  return `${dialogueId}:${turnIndex}`
}

export function wasScenarioTurnSpoken(storage: Pick<Storage, 'getItem'>, dialogueId: string, turnIndex: number) {
  try {
    return Number(storage.getItem(`${STORAGE_PREFIX}:${dialogueId}`) || 0) >= turnIndex
  } catch {
    return false
  }
}

export function markScenarioTurnSpoken(storage: Pick<Storage, 'setItem'>, dialogueId: string, turnIndex: number) {
  try {
    storage.setItem(`${STORAGE_PREFIX}:${dialogueId}`, String(turnIndex))
  } catch {
    // Private browsing and storage policies must not block the training loop.
  }
}
