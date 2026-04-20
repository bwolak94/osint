import { apiClient } from '@/shared/api/client'
import type { TechReconListResponse, TechReconRequest, TechReconScan } from './types'

export const techReconApi = {
  run: (body: TechReconRequest): Promise<TechReconScan> =>
    apiClient.post<TechReconScan>('/tech-recon/', body).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<TechReconListResponse> =>
    apiClient
      .get<TechReconListResponse>('/tech-recon/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<TechReconScan> =>
    apiClient.get<TechReconScan>(`/tech-recon/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/tech-recon/${id}`).then(() => undefined),
}
