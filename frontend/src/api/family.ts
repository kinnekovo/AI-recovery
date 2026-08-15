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
  }
}
