import { apiClient } from '@/shared/api/client'
import type { DomainPermutationScan, DomainPermutationListResponse } from './types'

export const domainPermutationApi = {
  scan: (domain: string): Promise<DomainPermutationScan> =>
    apiClient.post<DomainPermutationScan>('/domain-permutation/', { domain }).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<DomainPermutationListResponse> =>
    apiClient
      .get<DomainPermutationListResponse>('/domain-permutation/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<DomainPermutationScan> =>
    apiClient.get<DomainPermutationScan>(`/domain-permutation/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/domain-permutation/${id}`).then(() => undefined),
}
