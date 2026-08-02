import { http, request } from './http'
import type { LatestReport } from '@/types/api'

export const reportsApi = {
  latest() {
    return request<LatestReport>(http.get('/reports/latest'))
  }
}
