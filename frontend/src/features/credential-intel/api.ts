import { apiClient } from '@/shared/api/client'
import type { CredentialIntelListResponse, CredentialIntelRequest, CredentialIntelScan } from './types'

export const credentialIntelApi = {
  run: (body: CredentialIntelRequest): Promise<CredentialIntelScan> =>
    apiClient.post<CredentialIntelScan>('/credential-intel/', body).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<CredentialIntelListResponse> =>
    apiClient
      .get<CredentialIntelListResponse>('/credential-intel/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<CredentialIntelScan> =>
    apiClient.get<CredentialIntelScan>(`/credential-intel/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/credential-intel/${id}`).then(() => undefined),
}
