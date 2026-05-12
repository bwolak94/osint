import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  scanInstagramIntel,
  listInstagramIntelScans,
  deleteInstagramIntelScan,
} from './api'
import { toast } from '@/shared/components/Toast'
import type { QueryType } from './types'

const IG_INTEL_KEY = 'instagram-intel'

export function useScanInstagramIntel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ query, queryType }: { query: string; queryType: QueryType }) =>
      scanInstagramIntel(query, queryType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [IG_INTEL_KEY] })
      toast.success('Instagram Intel scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

export function useInstagramIntelHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [IG_INTEL_KEY, page, pageSize],
    queryFn: () => listInstagramIntelScans(page, pageSize),
  })
}

export function useDeleteInstagramIntelScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteInstagramIntelScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [IG_INTEL_KEY] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete'),
  })
}
