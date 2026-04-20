import { apiClient } from '@/shared/api/client'
import type { ImintListResponse, ImintRequest, ImintScan } from './types'

export const imintApi = {
  run: (body: ImintRequest): Promise<ImintScan> =>
    apiClient.post<ImintScan>('/imint/', body).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<ImintListResponse> =>
    apiClient
      .get<ImintListResponse>('/imint/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<ImintScan> =>
    apiClient.get<ImintScan>(`/imint/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/imint/${id}`).then(() => undefined),
}
