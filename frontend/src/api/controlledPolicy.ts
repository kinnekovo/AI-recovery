import { http, request } from './http'
import type { ControlledHistory, ControlledProposal, JsonObject } from '@/types/professional'

export const controlledPolicyApi = {
  proposals: (patientId: string) => request<ControlledProposal[]>(http.get(`/therapist/patients/${patientId}/policy-v2/proposals`)),
  proposal: (patientId: string, proposalId: string) => request<ControlledProposal>(http.get(`/therapist/patients/${patientId}/policy-v2/proposals/${proposalId}`)),
  create: (patientId: string, decisionId: string, payload: { action_type: ControlledProposal['action_type']; target_training_session_id: string }) => request<ControlledProposal>(http.post(`/therapist/patients/${patientId}/policy-v2/${decisionId}/proposals`, payload)),
  approve: (patientId: string, proposalId: string, comment?: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/proposals/${proposalId}/approve`, { comment: comment || null })),
  reject: (patientId: string, proposalId: string, reasonCode: string, comment?: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/proposals/${proposalId}/reject`, { reason_code: reasonCode, comment: comment || null })),
  apply: (patientId: string, proposalId: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/proposals/${proposalId}/apply`)),
  rollback: (patientId: string, executionId: string, reasonCode: string, comment?: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/executions/${executionId}/rollback`, { reason_code: reasonCode, comment: comment || null })),
  observe: (patientId: string, executionId: string, outcome: string, feedback?: string) => request<JsonObject>(http.post(`/therapist/patients/${patientId}/policy-v2/executions/${executionId}/observe`, { outcome, therapist_feedback: feedback || null })),
  history: (patientId: string) => request<ControlledHistory>(http.get(`/therapist/patients/${patientId}/policy-v2/controlled-actions/history`))
}
