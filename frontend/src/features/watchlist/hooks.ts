import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { watchlistApi } from './api'
import { toast } from '@/shared/components/Toast'
import type { WatchItem, CreateWatchItemRequest } from './types'

const KEY = 'watchlist'

export function useWatchlist() {
  return useQuery({
    queryKey: [KEY],
    queryFn: () => watchlistApi.list(),
  })
}

export function useCreateWatchItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateWatchItemRequest) => watchlistApi.create(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY] })
      toast.success('Watch item created')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to create watch item'),
  })
}

export function useUpdateWatchItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<WatchItem> }) =>
      watchlistApi.update(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY] })
      toast.success('Watch item updated')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to update watch item'),
  })
}

export function useDeleteWatchItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => watchlistApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY] })
      toast.success('Watch item deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete watch item'),
  })
}

export function useTriggerWatchItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => watchlistApi.trigger(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY] })
      toast.success('Scan triggered successfully')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to trigger scan'),
  })
}
