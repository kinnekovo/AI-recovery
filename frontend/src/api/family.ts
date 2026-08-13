import { http, request } from './http'
import type { FamilyObservation } from '@/types/api'

export const familyApi = {
  observation() {
    return request<FamilyObservation>(http.get('/family/observation'))
  }
}
