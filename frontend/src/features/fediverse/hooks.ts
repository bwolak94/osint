import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scanFediverse, listFediverseScans, deleteFediverseScan } from './api'
import { toast } from '@/shared/components/Toast'

const FEDIVERSE_KEY = 'fediverse'

export function useScanFediverse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (query: string) => scanFediverse(query),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEDIVERSE_KEY] })
      toast.success('Fediverse scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

export function useFediverseHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [FEDIVERSE_KEY, page, pageSize],
    queryFn: () => listFediverseScans(page, pageSize),
  })
}

export function useDeleteFediverseScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteFediverseScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEDIVERSE_KEY] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete'),
  })
}
