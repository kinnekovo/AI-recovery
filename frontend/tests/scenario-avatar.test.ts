import { describe, expect, it } from 'vitest'
import { latestAgentTurn, markScenarioTurnSpoken, scenarioTurnToken, wasScenarioTurnSpoken } from '@/features/training-session/scenarioAvatar'
import type { ScenarioDialogue } from '@/types/api'

function dialogue(turns: ScenarioDialogue['turns']): ScenarioDialogue {
  return {
    id: 'dialogue-1',
    status: 'active',
    current_state: 'collecting',
    patient_turn_count: 0,
    prompt_count: 0,
    maximum_prompt_level: 0,
    communication_goal: '完成购物表达',
    turns,
  }
}

describe('scenario avatar turn orchestration', () => {
  it('selects only the latest assistant reply for playback', () => {
    const result = latestAgentTurn(dialogue([
      { turn_index: 1, speaker: 'agent', dialogue_act: 'opening', text: '您好，需要什么？', created_at: '' },
      { turn_index: 2, speaker: 'patient', dialogue_act: 'response', text: '我想买牛奶。', created_at: '' },
      { turn_index: 3, speaker: 'agent', dialogue_act: 'follow_up', text: '需要几盒？', created_at: '' },
    ]))

    expect(result?.turn_index).toBe(3)
    expect(result?.text).toBe('需要几盒？')
  })

  it('persists the highest spoken turn to prevent reactive replay', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value) },
    }

    expect(wasScenarioTurnSpoken(storage, 'dialogue-1', 1)).toBe(false)
    markScenarioTurnSpoken(storage, 'dialogue-1', 3)
    expect(wasScenarioTurnSpoken(storage, 'dialogue-1', 2)).toBe(true)
    expect(wasScenarioTurnSpoken(storage, 'dialogue-1', 4)).toBe(false)
    expect(scenarioTurnToken('dialogue-1', 3)).toBe('dialogue-1:3')
  })

  it('keeps training available when browser storage is unavailable', () => {
    const blockedStorage = {
      getItem: () => { throw new Error('blocked') },
      setItem: () => { throw new Error('blocked') },
    }

    expect(wasScenarioTurnSpoken(blockedStorage, 'dialogue-1', 1)).toBe(false)
    expect(() => markScenarioTurnSpoken(blockedStorage, 'dialogue-1', 1)).not.toThrow()
  })
})
