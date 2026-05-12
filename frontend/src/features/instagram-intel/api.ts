import { apiClient } from '@/shared/api/client'
import type { InstagramIntelScan, InstagramIntelListResponse, QueryType } from './types'

const BASE = '/instagram-intel'

export const scanInstagramIntel = (
  query: string,
  query_type: QueryType,
): Promise<InstagramIntelScan> =>
  apiClient
    .post<InstagramIntelScan>(`${BASE}/`, { query, query_type })
    .then((r) => r.data)

export const listInstagramIntelScans = (
  page: number,
  pageSize: number,
): Promise<InstagramIntelListResponse> =>
  apiClient
    .get<InstagramIntelListResponse>(`${BASE}/`, { params: { page, page_size: pageSize } })
    .then((r) => r.data)

export const getInstagramIntelScan = (id: string): Promise<InstagramIntelScan> =>
  apiClient.get<InstagramIntelScan>(`${BASE}/${id}`).then((r) => r.data)

export const deleteInstagramIntelScan = (id: string): Promise<void> =>
  apiClient.delete(`${BASE}/${id}`).then(() => undefined)
