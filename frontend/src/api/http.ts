import axios from 'axios'
import type { ApiEnvelope } from '@/types/api'

export const http = axios.create({
  baseURL: '/api',
  timeout: 20000
})

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly detail?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function request<T>(promise: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
  try {
    const response = await promise
    if (response.data.code !== 0) {
      throw new Error(response.data.message)
    }
    return response.data.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status
      const message = readApiError(err.response?.data) || httpStatusMessage(status) || axiosErrorMessage(err)
      if (status === 401 && window.location.pathname !== '/login') {
        localStorage.removeItem('access_token')
        window.location.assign('/login')
      }
      throw new ApiError(message, status, err.response?.data)
    }
    throw err
  }
}

function readApiError(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const payload = data as { detail?: unknown; message?: unknown }
  if (typeof payload.message === 'string') return payload.message
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => {
        if (!item || typeof item !== 'object') return ''
        const detailItem = item as { msg?: unknown; loc?: unknown }
        const field = Array.isArray(detailItem.loc) ? detailItem.loc.slice(-1)[0] : ''
        const message = typeof detailItem.msg === 'string' ? detailItem.msg : ''
        return field ? `${field}: ${message}` : message
      })
      .filter(Boolean)
      .join('；')
  }
  return ''
}

function httpStatusMessage(status?: number): string {
  if (status === 401) return '登录已过期，请重新登录。'
  if (status === 403) return '当前账号没有权限执行这个操作。'
  if (status === 404) return '请求的数据不存在或已被移除。'
  if (status === 409) return '当前状态与操作要求不一致，请刷新数据后重试。'
  if (status === 422) return '提交内容未通过校验，请检查表单。'
  if (status && status >= 500) return '服务器暂时无法完成请求，请稍后再试。'
  return ''
}

function axiosErrorMessage(error: { code?: string; message?: string }): string {
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' || error.message?.toLowerCase().includes('timeout')) {
    return '语音分析时间较长，服务仍可能在处理中。请稍候再查看，或稍后重试。'
  }
  return error.message || '网络请求失败，请稍后重试。'
}
