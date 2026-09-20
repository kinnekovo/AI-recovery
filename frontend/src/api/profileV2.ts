import { http, request } from './http'
import type { PatientProfileProjection, ProfileEvidence, ProfileSnapshot } from '@/types/professional'

export const profileV2Api = {
  patientProfile: () => request<PatientProfileProjection>(http.get('/patient/profile')),
  latest: (patientId: string) => request<ProfileSnapshot>(http.get(`/therapist/patients/${patientId}/profile`)),
  history: (patientId: string) => request<ProfileSnapshot[]>(http.get(`/therapist/patients/${patientId}/profile/history`)),
  evidence: (patientId: string, snapshotId: string) => request<ProfileEvidence[]>(http.get(`/therapist/patients/${patientId}/profile/${snapshotId}/evidence`)),
  rebuild: (patientId: string) => request<ProfileSnapshot>(http.post(`/therapist/patients/${patientId}/profile/rebuild`))
}
