import { http, request } from './http'
import type { HealthStatus } from '@/types/api'

export const healthApi = {
  status() {
    return request<HealthStatus>(http.get('/health'))
  }
}
