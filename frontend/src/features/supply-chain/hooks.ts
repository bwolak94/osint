import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supplyChainApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'supply-chain'

export function useScanSupplyChain() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ target, targetType }: { target: string; targetType: string }) =>
      supplyChainApi.scan(target, targetType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Supply chain scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

export function useSupplyChainHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => supplyChainApi.list(page, pageSize),
  })
}

export function useDeleteSupplyChainScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => supplyChainApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete'),
  })
}
