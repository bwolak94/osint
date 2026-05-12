import { apiClient } from '@/shared/api/client'
import type {
  Annotation,
  CreateAnnotationRequest,
  UpdateAnnotationRequest,
  Notification,
  CreateMentionRequest,
} from './types'

export const annotationsApi = {
  list: (investigationId: string, targetId?: string): Promise<Annotation[]> =>
    apiClient
      .get<Annotation[]>(`/investigations/${investigationId}/annotations`, {
        params: targetId ? { target_id: targetId } : undefined,
      })
      .then((r) => r.data),

  create: (investigationId: string, body: CreateAnnotationRequest): Promise<Annotation> =>
    apiClient
      .post<Annotation>(`/investigations/${investigationId}/annotations`, body)
      .then((r) => r.data),

  update: (annotationId: string, body: UpdateAnnotationRequest): Promise<Annotation> =>
    apiClient
      .patch<Annotation>(`/annotations/${annotationId}`, body)
      .then((r) => r.data),

  delete: (annotationId: string): Promise<void> =>
    apiClient.delete(`/annotations/${annotationId}`).then(() => undefined),
}

export const mentionsApi = {
  create: (body: CreateMentionRequest): Promise<void> =>
    apiClient.post('/mentions', body).then(() => undefined),
}

export const notificationsApi = {
  list: (): Promise<Notification[]> =>
    apiClient.get<Notification[]>('/notifications').then((r) => r.data),

  markRead: (notificationId: string): Promise<void> =>
    apiClient.post(`/notifications/${notificationId}/read`).then(() => undefined),

  markAllRead: (): Promise<void> =>
    apiClient.post('/notifications/read-all').then(() => undefined),
}
