import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { stealerLogsApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'stealer-logs'

export function useQueryStealerLogs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ query, queryType }: { query: string; queryType: string }) =>
      stealerLogsApi.query(query, queryType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Stealer log query completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Query failed'),
  })
}

export function useStealerLogHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => stealerLogsApi.list(page, pageSize),
  })
}

export function useDeleteStealerCheck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => stealerLogsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete'),
  })
}
