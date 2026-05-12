import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  scanFacebookIntel,
  listFacebookIntelScans,
  deleteFacebookIntelScan,
} from './api'
import { toast } from '@/shared/components/Toast'
import type { QueryType } from './types'

const FB_INTEL_KEY = 'facebook-intel'

export function useScanFacebookIntel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ query, queryType }: { query: string; queryType: QueryType }) =>
      scanFacebookIntel(query, queryType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FB_INTEL_KEY] })
      toast.success('Facebook Intel scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

export function useFacebookIntelHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [FB_INTEL_KEY, page, pageSize],
    queryFn: () => listFacebookIntelScans(page, pageSize),
  })
}

export function useDeleteFacebookIntelScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteFacebookIntelScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FB_INTEL_KEY] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete'),
  })
}
