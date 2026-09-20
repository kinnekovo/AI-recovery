import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ControlledActionsPanel from '@/components/therapist/ControlledActionsPanel.vue'
import { controlledPolicyApi } from '@/api/controlledPolicy'
import type { ControlledProposal } from '@/types/professional'

vi.mock('@/api/controlledPolicy', () => ({ controlledPolicyApi: { proposals: vi.fn(), history: vi.fn(), create: vi.fn(), approve: vi.fn(), reject: vi.fn(), apply: vi.fn(), rollback: vi.fn(), observe: vi.fn() } }))

const proposal = (status: string, reasons: string[] = []): ControlledProposal => ({ id: status, policy_decision_id: 'd', patient_profile_id: 'p', target_training_session_id: 's', action_type: 'training_focus_override', proposed_value: {}, current_value: {}, expected_scope: {}, reason_codes: reasons, policy_version: 'policy-v2.0', rules_version: 'rules-v1', validation_run_id: null, profile_snapshot_id: null, activation_policy_version: 'controlled-v1', status, expires_at: '2026-01-01T00:00:00Z', created_at: '2026-01-01T00:00:00Z' })

describe('controlled activation safety UI', () => {
  beforeEach(() => { vi.mocked(controlledPolicyApi.history).mockResolvedValue({ proposals: [], analytics: {} }) })
  it('does not offer Apply before approval', async () => {
    vi.mocked(controlledPolicyApi.proposals).mockResolvedValue([proposal('pending_review')])
    const wrapper = mount(ControlledActionsPanel, { props: { patientId: 'patient' } }); await flushPromises()
    expect(wrapper.text()).toContain('批准'); expect(wrapper.text()).not.toContain('确认应用到本次训练')
  })
  it('offers explicit Apply only for approved proposals and blocks suspended actions', async () => {
    vi.mocked(controlledPolicyApi.proposals).mockResolvedValue([proposal('approved'), proposal('suspended', ['suspended'])])
    const wrapper = mount(ControlledActionsPanel, { props: { patientId: 'patient' } }); await flushPromises()
    expect(wrapper.findAll('button').some(button => button.text().includes('确认应用到本次训练'))).toBe(true)
    expect(wrapper.text()).toContain('当前该类型受控操作已暂停')
  })
})
