import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PatientProfileView from '@/views/patient/PatientProfileView.vue'
import { profileV2Api } from '@/api/profileV2'

vi.mock('@/api/profileV2', () => ({ profileV2Api: { patientProfile: vi.fn() } }))

describe('patient-safe Profile V2', () => {
  beforeEach(() => vi.mocked(profileV2Api.patientProfile).mockReset())
  it('uses a natural empty state and hides professional vocabulary', async () => {
    vi.mocked(profileV2Api.patientProfile).mockResolvedValue({ status: 'insufficient', freshness: 'building', dimensions: [], limitations: [] })
    const wrapper = mount(PatientProfileView)
    await flushPromises()
    expect(wrapper.text()).toContain('完成更多训练或评估后')
    expect(wrapper.text()).not.toContain('insufficient_evidence')
    expect(wrapper.text()).not.toContain('PolicyDecision')
  })
})
