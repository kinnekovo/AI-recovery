import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

describe('role-aware route guards', () => {
  beforeEach(() => { setActivePinia(createPinia()); const auth=useAuthStore(); auth.token='token'; localStorage.setItem('access_token','token') })
  it('denies a patient professional routes', async () => {
    const auth=useAuthStore(); auth.me={ user: { id:'p',username:'patient',role:'patient',status:'active',created_at:'' }, profile: null } as never
    await router.push('/therapist/governance')
    expect(router.currentRoute.value.path).toBe('/home')
  })
  it('denies a therapist patient-owned routes', async () => {
    const auth=useAuthStore(); auth.me={ user: { id:'t',username:'therapist',role:'therapist',status:'active',created_at:'' }, profile: null } as never
    await router.push('/patient/profile')
    expect(router.currentRoute.value.path).toBe('/therapist')
  })
})
