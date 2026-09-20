import { http, request } from './http'
import type { GovernanceRun, JsonObject, RegistryEntry } from '@/types/professional'

export const governanceApi = {
  createDataset: (name: string, version: string) => request<{ id: string; status: string; version: string }>(http.post('/therapist/policy-v2/controlled-governance/datasets', null, { params: { name, version } })),
  addItem: (datasetId: string, proposalId: string) => request<JsonObject>(http.post(`/therapist/policy-v2/controlled-governance/datasets/${datasetId}/items/${proposalId}`)),
  removeItem: (datasetId: string, itemId: string) => request<JsonObject>(http.delete(`/therapist/policy-v2/controlled-governance/datasets/${datasetId}/items/${itemId}`)),
  freeze: (datasetId: string) => request<JsonObject>(http.post(`/therapist/policy-v2/controlled-governance/datasets/${datasetId}/freeze`)),
  run: (datasetId: string, actionType?: string) => request<GovernanceRun[]>(http.post('/therapist/policy-v2/controlled-governance/runs', null, { params: { dataset_id: datasetId, ...(actionType ? { action_type: actionType } : {}) } })),
  registry: () => request<RegistryEntry[]>(http.get('/therapist/policy-v2/controlled-governance/registry')),
  registryDetail: (policyVersion: string, rulesVersion: string, actionType: string) => request<JsonObject>(http.get(`/therapist/policy-v2/controlled-governance/registry/${encodeURIComponent(policyVersion)}/${encodeURIComponent(rulesVersion)}/${encodeURIComponent(actionType)}`))
}
