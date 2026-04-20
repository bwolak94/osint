import { apiClient } from '@/shared/api/client'
import type { SocmintListResponse, SocmintRequest, SocmintScan } from './types'

export const socmintApi = {
  run: (body: SocmintRequest): Promise<SocmintScan> =>
    apiClient.post<SocmintScan>('/socmint/', body).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<SocmintListResponse> =>
    apiClient
      .get<SocmintListResponse>('/socmint/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<SocmintScan> =>
    apiClient.get<SocmintScan>(`/socmint/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/socmint/${id}`).then(() => undefined),
}
