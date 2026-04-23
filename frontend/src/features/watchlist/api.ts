import { apiClient } from '@/shared/api/client'
import type { WatchItem, CreateWatchItemRequest } from './types'

export const watchlistApi = {
  list: (): Promise<WatchItem[]> =>
    apiClient.get<WatchItem[]>('/api/v1/watchlist').then((r) => r.data),

  create: (body: CreateWatchItemRequest): Promise<WatchItem> =>
    apiClient.post<WatchItem>('/api/v1/watchlist', body).then((r) => r.data),

  update: (id: string, body: Partial<WatchItem>): Promise<WatchItem> =>
    apiClient.patch<WatchItem>(`/api/v1/watchlist/${id}`, body).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/api/v1/watchlist/${id}`).then(() => undefined),

  trigger: (id: string): Promise<{ status: string }> =>
    apiClient.post<{ status: string }>(`/api/v1/watchlist/${id}/trigger`).then((r) => r.data),
}
