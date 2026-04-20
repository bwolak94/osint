import { apiClient } from '@/shared/api/client'
import type { StealerLogCheck, StealerLogListResponse } from './types'

export const stealerLogsApi = {
  query: (query: string, queryType: string): Promise<StealerLogCheck> =>
    apiClient.post<StealerLogCheck>('/stealer-logs/', { query, query_type: queryType }).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<StealerLogListResponse> =>
    apiClient
      .get<StealerLogListResponse>('/stealer-logs/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<StealerLogCheck> =>
    apiClient.get<StealerLogCheck>(`/stealer-logs/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/stealer-logs/${id}`).then(() => undefined),
}
