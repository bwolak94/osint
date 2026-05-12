import { apiClient } from '@/shared/api/client'
import type { FacebookIntelScan, FacebookIntelListResponse, QueryType } from './types'

const BASE = '/facebook-intel'

export const scanFacebookIntel = (
  query: string,
  query_type: QueryType,
): Promise<FacebookIntelScan> =>
  apiClient
    .post<FacebookIntelScan>(`${BASE}/`, { query, query_type })
    .then((r) => r.data)

export const listFacebookIntelScans = (
  page: number,
  pageSize: number,
): Promise<FacebookIntelListResponse> =>
  apiClient
    .get<FacebookIntelListResponse>(`${BASE}/`, { params: { page, page_size: pageSize } })
    .then((r) => r.data)

export const getFacebookIntelScan = (id: string): Promise<FacebookIntelScan> =>
  apiClient.get<FacebookIntelScan>(`${BASE}/${id}`).then((r) => r.data)

export const deleteFacebookIntelScan = (id: string): Promise<void> =>
  apiClient.delete(`${BASE}/${id}`).then(() => undefined)
