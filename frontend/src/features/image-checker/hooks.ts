import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { imageCheckerApi } from './api'
import { toast } from '@/shared/components/Toast'

const IMAGE_CHECKER_KEY = 'image-checker'

export function useUploadImage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => imageCheckerApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [IMAGE_CHECKER_KEY, 'history'] })
      toast.success('Image analyzed successfully')
    },
    onError: (e: Error) => {
      toast.error(e.message ?? 'Failed to analyze image')
    },
  })
}

export function useImageHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: [IMAGE_CHECKER_KEY, 'history', page, pageSize],
    queryFn: () => imageCheckerApi.list(page, pageSize),
  })
}

export function useDeleteImageCheck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => imageCheckerApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [IMAGE_CHECKER_KEY, 'history'] })
      toast.success('Record deleted')
    },
    onError: (e: Error) => {
      toast.error(e.message ?? 'Failed to delete record')
    },
  })
}
