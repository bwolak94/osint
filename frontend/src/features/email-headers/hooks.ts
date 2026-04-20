import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { emailHeadersApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'email-headers'

export function useAnalyzeEmailHeaders() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (rawHeaders: string) => emailHeadersApi.analyze(rawHeaders),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Email headers analyzed successfully')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to analyze headers'),
  })
}

export function useEmailHeaderHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => emailHeadersApi.list(page, pageSize),
  })
}

export function useDeleteEmailCheck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => emailHeadersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete record'),
  })
}
