import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AsyncState from '@/components/common/AsyncState.vue'

describe('AsyncState', () => {
  it('renders loading, empty, error and success without a blank screen', async () => {
    const wrapper = mount(AsyncState, { props: { loading: true }, slots: { default: '<p>success</p>' } })
    expect(wrapper.get('[role=status]').text()).toContain('正在加载')
    await wrapper.setProps({ loading: false, empty: true, emptyText: '没有证据' })
    expect(wrapper.text()).toContain('没有证据')
    await wrapper.setProps({ empty: false, error: '业务冲突' })
    expect(wrapper.get('[role=alert]').text()).toContain('业务冲突')
    await wrapper.setProps({ error: '' })
    expect(wrapper.text()).toContain('success')
  })
})
