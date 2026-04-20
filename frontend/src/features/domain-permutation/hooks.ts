import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { domainPermutationApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'domain-permutation'

export function useScanDomainPermutations() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (domain: string) => domainPermutationApi.scan(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Domain scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to scan domain'),
  })
}

export function useDomainPermutationHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => domainPermutationApi.list(page, pageSize),
  })
}

export function useDeleteDomainScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => domainPermutationApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete record'),
  })
}
