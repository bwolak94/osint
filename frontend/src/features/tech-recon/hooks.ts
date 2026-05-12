import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/components/Toast'
import { techReconApi } from './api'
import type { TechReconRequest } from './types'

const KEY = 'tech-recon'

export function useRunTechRecon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TechReconRequest) => techReconApi.run(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
    },
    onError: (e: Error) => toast.error(e.message ?? 'Tech recon scan failed'),
  })
}

export function useTechReconHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => techReconApi.list(page, pageSize),
  })
}

export function useDeleteTechRecon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => techReconApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Scan deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete scan'),
  })
}
