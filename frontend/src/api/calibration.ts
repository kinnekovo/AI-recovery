import { http, request } from './http'
import type { CalibrationDataset, CalibrationReport, CalibrationRunResult, JsonObject, MetricRegistry } from '@/types/professional'

export const calibrationApi = {
  createDataset: (payload: { name: string; version: string; description?: string }) => request<{ id: string }>(http.post('/calibration/datasets', payload)),
  dataset: (id: string) => request<CalibrationDataset>(http.get(`/calibration/datasets/${id}`)),
  addSample: (id: string, evaluationRunId: string, dimensionCode: string) => request<{ id: string }>(http.post(`/calibration/datasets/${id}/samples`, { evaluation_run_id: evaluationRunId, dimension_code: dimensionCode })),
  removeSample: (id: string, sampleId: string) => request<{ deleted: boolean }>(http.delete(`/calibration/datasets/${id}/samples/${sampleId}`)),
  freeze: (id: string) => request<{ id: string; status: string }>(http.post(`/calibration/datasets/${id}/freeze`)),
  annotate: (payload: JsonObject) => request<{ id: string }>(http.post('/calibration/annotations', payload)),
  adjudicate: (payload: JsonObject) => request<{ id: string; reference_source: string }>(http.post('/calibration/annotations/adjudicate', payload)),
  registerMetric: (payload: JsonObject) => request<{ id: string }>(http.post('/calibration/metrics', payload)),
  metric: (code: string) => request<MetricRegistry>(http.get(`/calibration/metrics/${code}`)),
  run: (datasetId: string, metricCode: string) => request<CalibrationRunResult>(http.post('/calibration/runs', { dataset_id: datasetId, metric_code: metricCode })),
  report: (runId: string) => request<CalibrationReport>(http.get(`/calibration/runs/${runId}/report`))
}
