import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { docMetadataApi } from './api'
import { toast } from '@/shared/components/Toast'

const KEY = 'doc-metadata'

export function useUploadDoc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => docMetadataApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Document analyzed successfully')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to analyze document'),
  })
}

export function useDocHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [KEY, 'history', page, pageSize],
    queryFn: () => docMetadataApi.list(page, pageSize),
  })
}

export function useDeleteDoc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => docMetadataApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete record'),
  })
}
