import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { macLookupApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'mac-lookup'

export function useMacLookup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (macAddress: string) => macLookupApi.lookup(macAddress),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('MAC address resolved successfully')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to resolve MAC address'),
  })
}

export function useMacLookupHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => macLookupApi.list(page, pageSize),
  })
}

export function useDeleteMacLookup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => macLookupApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete record'),
  })
}
