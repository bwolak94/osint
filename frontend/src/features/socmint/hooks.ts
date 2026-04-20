import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/components/Toast'
import { socmintApi } from './api'
import type { SocmintRequest } from './types'

const KEY = 'socmint'

export function useRunSocmint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: SocmintRequest) => socmintApi.run(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
    },
    onError: (e: Error) => toast.error(e.message ?? 'SOCMINT scan failed'),
  })
}

export function useSocmintHistory(page: number, pageSize = 20) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => socmintApi.list(page, pageSize),
  })
}

export function useDeleteSocmint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => socmintApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Scan deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete scan'),
  })
}
