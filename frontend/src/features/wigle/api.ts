import { apiClient } from '@/shared/api/client'
import type { WigleScan, WigleListResponse } from './types'

const BASE = '/wigle'

export const wigleApi = {
  searchWigle: (query: string, queryType: string): Promise<WigleScan> =>
    apiClient
      .post<WigleScan>(`${BASE}/`, { query, query_type: queryType })
      .then((r) => r.data),

  listWigleScans: (page: number, pageSize: number): Promise<WigleListResponse> =>
    apiClient
      .get<WigleListResponse>(`${BASE}/`, { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  getWigleScan: (id: string): Promise<WigleScan> =>
    apiClient.get<WigleScan>(`${BASE}/${id}`).then((r) => r.data),

  deleteWigleScan: (id: string): Promise<void> =>
    apiClient.delete(`${BASE}/${id}`).then(() => undefined),
}
