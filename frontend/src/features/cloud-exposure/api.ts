import { apiClient } from '@/shared/api/client'
import type { CloudExposureScan, CloudExposureListResponse } from './types'

export const cloudExposureApi = {
  scan: (target: string): Promise<CloudExposureScan> =>
    apiClient.post<CloudExposureScan>('/cloud-exposure/', { target }).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<CloudExposureListResponse> =>
    apiClient
      .get<CloudExposureListResponse>('/cloud-exposure/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<CloudExposureScan> =>
    apiClient.get<CloudExposureScan>(`/cloud-exposure/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/cloud-exposure/${id}`).then(() => undefined),
}
