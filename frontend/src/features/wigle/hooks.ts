import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { wigleApi } from './api'
import { toast } from '@/shared/components/Toast'

const WIGLE_KEY = 'wigle'

export function useSearchWigle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ query, queryType }: { query: string; queryType: string }) =>
      wigleApi.searchWigle(query, queryType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [WIGLE_KEY] })
      toast.success('WiGLE search completed')
    },
    onError: (e: Error) => {
      toast.error(e.message ?? 'Search failed')
    },
  })
}

export function useWigleHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [WIGLE_KEY, page, pageSize],
    queryFn: () => wigleApi.listWigleScans(page, pageSize),
  })
}

export function useDeleteWigleScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => wigleApi.deleteWigleScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [WIGLE_KEY] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => {
      toast.error(e.message ?? 'Failed to delete record')
    },
  })
}
