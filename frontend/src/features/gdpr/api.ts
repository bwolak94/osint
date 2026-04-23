import { apiClient } from '@/shared/api/client'
import type { GdprReport, GdprSubjectRequest } from './types'

export const gdprApi = {
  createSubjectRequest: (request: GdprSubjectRequest): Promise<GdprReport> =>
    apiClient
      .post<GdprReport>('/gdpr/subject-requests', request)
      .then((r) => r.data),

  listSubjectRequests: (): Promise<GdprReport[]> =>
    apiClient.get<GdprReport[]>('/gdpr/subject-requests').then((r) => r.data),

  getSubjectRequest: (reportId: string): Promise<GdprReport> =>
    apiClient
      .get<GdprReport>(`/gdpr/subject-requests/${reportId}`)
      .then((r) => r.data),
}
