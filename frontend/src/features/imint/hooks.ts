import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/components/Toast'
import { imintApi } from './api'
import type { ImintRequest } from './types'

const KEY = 'imint'

export function useRunImint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ImintRequest) => imintApi.run(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
    },
    onError: (e: Error) => toast.error(e.message ?? 'IMINT scan failed'),
  })
}

export function useImintHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => imintApi.list(page, pageSize),
  })
}

export function useDeleteImint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => imintApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Scan deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete scan'),
  })
}
