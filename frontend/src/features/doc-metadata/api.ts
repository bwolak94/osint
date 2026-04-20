import { apiClient } from '@/shared/api/client'
import type { DocMetadata, DocMetadataListResponse } from './types'

export const docMetadataApi = {
  upload: (file: File): Promise<DocMetadata> => {
    const form = new FormData()
    form.append('file', file)
    return apiClient
      .post<DocMetadata>('/doc-metadata/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },

  list: (page: number, pageSize: number): Promise<DocMetadataListResponse> =>
    apiClient
      .get<DocMetadataListResponse>('/doc-metadata/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<DocMetadata> =>
    apiClient.get<DocMetadata>(`/doc-metadata/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/doc-metadata/${id}`).then(() => undefined),
}
