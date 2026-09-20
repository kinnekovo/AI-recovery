import { describe, expect, it } from 'vitest'
import { presentStatus } from '@/utils/status'
import { explainReasonCode } from '@/utils/reasonCodes'

describe('professional vocabulary', () => {
  it('explains shadow and governance states without implying activation', () => {
    expect(presentStatus('shadow').description).toContain('不会自动改变')
    expect(presentStatus('eligible_for_streamlined_evaluation').description).toContain('仍需治疗师审批')
    expect(presentStatus('manual_only').label).toContain('人工')
    expect(presentStatus('suspended').tone).toBe('danger')
  })
  it('shows human text and keeps the raw reason code available', () => {
    expect(explainReasonCode('unexpected_decision_instability')).toBe('决策稳定性需要复核')
    expect(explainReasonCode('NEW_BACKEND_CODE')).toBe('new backend code')
  })
})
