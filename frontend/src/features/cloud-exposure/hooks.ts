import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { cloudExposureApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'cloud-exposure'

export function useScanCloudExposure() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (target: string) => cloudExposureApi.scan(target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Cloud exposure scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

export function useCloudExposureHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => cloudExposureApi.list(page, pageSize),
  })
}

export function useDeleteCloudScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cloudExposureApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete record'),
  })
}
