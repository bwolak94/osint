import { apiClient } from '@/shared/api/client'
import type { MacLookup, MacLookupListResponse } from './types'

export const macLookupApi = {
  lookup: (macAddress: string): Promise<MacLookup> =>
    apiClient.post<MacLookup>('/mac-lookup/', { mac_address: macAddress }).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<MacLookupListResponse> =>
    apiClient.get<MacLookupListResponse>('/mac-lookup/', { params: { page, page_size: pageSize } }).then((r) => r.data),

  get: (id: string): Promise<MacLookup> =>
    apiClient.get<MacLookup>(`/mac-lookup/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/mac-lookup/${id}`).then(() => undefined),
}
