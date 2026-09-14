import { http, request } from './http'
import type { AvatarVideoTask } from '@/types/api'

export const avatarVideosApi = {
  get(taskId: string) {
    return request<AvatarVideoTask>(http.get(`/avatar-video-tasks/${taskId}`))
  }
}
