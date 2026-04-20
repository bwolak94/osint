import { apiClient } from '@/shared/api/client'
import type { ImageCheck, ImageCheckListResponse } from './types'

export const imageCheckerApi = {
  upload: (file: File): Promise<ImageCheck> => {
    const form = new FormData()
    form.append('file', file)
    return apiClient
      .post<ImageCheck>('/image-checker/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },

  list: (page: number, pageSize: number): Promise<ImageCheckListResponse> =>
    apiClient
      .get<ImageCheckListResponse>('/image-checker/', {
        params: { page, page_size: pageSize },
      })
      .then((r) => r.data),

  get: (id: string): Promise<ImageCheck> =>
    apiClient.get<ImageCheck>(`/image-checker/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/image-checker/${id}`).then(() => undefined),
}
