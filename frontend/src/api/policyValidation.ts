import { http, request } from './http'
import type { JsonObject, RegistryEntry } from '@/types/professional'

export const policyValidationApi = {
  createDataset: (name: string, version: string) => request<{ id: string; status: string; version: string }>(http.post('/therapist/policy-v2/validation/datasets', null, { params: { name, version } })),
  addDecision: (datasetId: string, decisionId: string) => request<JsonObject>(http.post(`/therapist/policy-v2/validation/datasets/${datasetId}/decisions/${decisionId}`)),
  freeze: (datasetId: string) => request<JsonObject>(http.post(`/therapist/policy-v2/validation/datasets/${datasetId}/freeze`)),
  run: (datasetId: string) => request<JsonObject>(http.post(`/therapist/policy-v2/validation/datasets/${datasetId}/runs`)),
  registry: () => request<RegistryEntry[]>(http.get('/therapist/policy-v2/validation/registry'))
}
