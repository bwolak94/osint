import { apiClient } from '@/shared/api/client'
import type { WatchItem, CreateWatchItemRequest } from './types'

export const watchlistApi = {
  list: (): Promise<WatchItem[]> =>
    apiClient.get<WatchItem[]>('/watchlist').then((r) => r.data),

  create: (body: CreateWatchItemRequest): Promise<WatchItem> =>
    apiClient.post<WatchItem>('/watchlist', body).then((r) => r.data),

  update: (id: string, body: Partial<WatchItem>): Promise<WatchItem> =>
    apiClient.patch<WatchItem>(`/watchlist/${id}`, body).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/watchlist/${id}`).then(() => undefined),

  trigger: (id: string): Promise<{ status: string }> =>
    apiClient.post<{ status: string }>(`/watchlist/${id}/trigger`).then((r) => r.data),
}
