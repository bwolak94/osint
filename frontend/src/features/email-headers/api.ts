import { apiClient } from '@/shared/api/client'
import type { EmailHeaderCheck, EmailHeaderListResponse } from './types'

export const emailHeadersApi = {
  analyze: (rawHeaders: string): Promise<EmailHeaderCheck> =>
    apiClient.post<EmailHeaderCheck>('/email-headers/', { raw_headers: rawHeaders }).then((r) => r.data),

  list: (page: number, pageSize: number): Promise<EmailHeaderListResponse> =>
    apiClient
      .get<EmailHeaderListResponse>('/email-headers/', { params: { page, page_size: pageSize } })
      .then((r) => r.data),

  get: (id: string): Promise<EmailHeaderCheck> =>
    apiClient.get<EmailHeaderCheck>(`/email-headers/${id}`).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/email-headers/${id}`).then(() => undefined),
}
