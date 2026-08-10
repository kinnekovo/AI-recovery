import { http, request } from './http'
import type { PatientProfile, User, UserRole } from '@/types/api'

export interface AuthResult {
  access_token: string
  token_type: string
  user: {
    id: string
    role: UserRole
  }
}

export interface MeResult {
  user: User
  patient_profile: PatientProfile | null
}

export const authApi = {
  register(username: string, password: string) {
    return request<{ user: User }>(http.post('/auth/register', { username, password, role: 'patient' }))
  },
  login(username: string, password: string) {
    return request<AuthResult>(http.post('/auth/login', { username, password }))
  },
  me() {
    return request<MeResult>(http.get('/users/me'))
  }
}
