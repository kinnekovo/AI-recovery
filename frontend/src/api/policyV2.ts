import { http, request } from './http'
import type { PolicyDecision, PolicyExplanation, JsonObject } from '@/types/professional'

export const policyV2Api = {
  latest: (patientId: string) => request<PolicyDecision>(http.get(`/therapist/patients/${patientId}/policy-v2/latest`)),
  history: (patientId: string) => request<PolicyDecision[]>(http.get(`/therapist/patients/${patientId}/policy-v2/history`)),
  explanation: (patientId: string, decisionId: string) => request<PolicyExplanation>(http.get(`/therapist/patients/${patientId}/policy-v2/${decisionId}/explanation`)),
  feedback: (patientId: string, decisionId: string, payload: { agreement: string; reason_codes: string[]; comment?: string | null }) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/${decisionId}/feedback`, payload)),
  observe: (patientId: string, decisionId: string, trainingSessionId: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/${decisionId}/observe`, { training_session_id: trainingSessionId }))
}
