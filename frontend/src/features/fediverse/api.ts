import { apiClient } from '@/shared/api/client'
import type { FediverseScan, FediverseListResponse } from './types'

const BASE = '/fediverse'

export const scanFediverse = (query: string): Promise<FediverseScan> =>
  apiClient.post<FediverseScan>(`${BASE}/`, { query }).then((r) => r.data)

export const listFediverseScans = (page: number, pageSize: number): Promise<FediverseListResponse> =>
  apiClient
    .get<FediverseListResponse>(`${BASE}/`, { params: { page, page_size: pageSize } })
    .then((r) => r.data)

export const getFediverseScan = (id: string): Promise<FediverseScan> =>
  apiClient.get<FediverseScan>(`${BASE}/${id}`).then((r) => r.data)

export const deleteFediverseScan = (id: string): Promise<void> =>
  apiClient.delete(`${BASE}/${id}`).then(() => undefined)
