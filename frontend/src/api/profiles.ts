import { http, request } from './http'
import type { AbilityProfile } from '@/types/api'

export const profilesApi = {
  ability() {
    return request<AbilityProfile>(http.get('/profile/ability'))
  }
}
