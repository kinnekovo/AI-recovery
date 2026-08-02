import axios from 'axios'
import type { ApiEnvelope } from '@/types/api'

export const http = axios.create({
  baseURL: '/api',
  timeout: 20000
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function request<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  const response = await promise
  if (response.data.code !== 0) {
    throw new Error(response.data.message)
  }
  return response.data.data
}
