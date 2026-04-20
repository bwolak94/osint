import { apiClient } from '@/shared/api/client'
import type { SupplyChainScan, SupplyChainListResponse } from './types'

export const supplyChainApi = {
  scan: (target: string, targetType: string): Promise<SupplyChainScan> =>
    apiClient.post<SupplyChainScan>('/supply-chain/', { target, target_type: targetType }).then((r) => r.data),
  list: (page: number, pageSize: number): Promise<SupplyChainListResponse> =>
    apiClient.get<SupplyChainListResponse>('/supply-chain/', { params: { page, page_size: pageSize } }).then((r) => r.data),
  get: (id: string): Promise<SupplyChainScan> =>
    apiClient.get<SupplyChainScan>(`/supply-chain/${id}`).then((r) => r.data),
  delete: (id: string): Promise<void> =>
    apiClient.delete(`/supply-chain/${id}`).then(() => undefined),
}
