import { http, request } from './http'
import type { FamilyBoundPatient, FamilyObservation } from '@/types/api'

export const familyApi = {
  patients() {
    return request<FamilyBoundPatient[]>(http.get('/family/patients'))
  },
  observation(patientUserId?: string | null) {
    return request<FamilyObservation>(
      http.get('/family/observation', {
        params: patientUserId ? { patient_user_id: patientUserId } : {}
      })
    )
  },
  confirmBinding(bindingId: string) {
    return request<FamilyBoundPatient>(http.post(`/family/bindings/${bindingId}/confirm`))
  },
  revokeBinding(bindingId: string) {
    return request<FamilyBoundPatient>(http.post(`/family/bindings/${bindingId}/revoke`))
  }
}
