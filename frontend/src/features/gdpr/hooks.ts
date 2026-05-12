import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gdprApi } from './api'
import { toast } from '@/shared/components/Toast'
import type { GdprSubjectRequest } from './types'

const KEY = 'gdpr'

export function useGdprReports() {
  return useQuery({
    queryKey: [KEY, 'reports'],
    queryFn: () => gdprApi.listSubjectRequests(),
  })
}

export function useGdprReport(reportId: string | null) {
  return useQuery({
    queryKey: [KEY, 'reports', reportId],
    queryFn: () => gdprApi.getSubjectRequest(reportId!),
    enabled: reportId !== null,
  })
}

export function useCreateGdprReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: GdprSubjectRequest) =>
      gdprApi.createSubjectRequest(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'reports'] })
      toast.success('Exposure check completed successfully')
    },
    onError: (e: Error) =>
      toast.error(e.message ?? 'Failed to run exposure check'),
  })
}
