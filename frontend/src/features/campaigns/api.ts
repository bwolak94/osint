import { apiClient } from '@/shared/api/client'
import type {
  Campaign,
  CampaignsListResponse,
  CreateCampaignPayload,
  UpdateCampaignPayload,
  AddInvestigationPayload,
  CampaignGraphResponse,
  SimilarCampaign,
} from './types'

export const campaignsApi = {
  list: (skip = 0, limit = 20): Promise<CampaignsListResponse> =>
    apiClient
      .get<CampaignsListResponse>('/campaigns', { params: { skip, limit } })
      .then((r) => r.data),

  get: (id: string): Promise<Campaign> =>
    apiClient.get<Campaign>(`/campaigns/${id}`).then((r) => r.data),

  create: (payload: CreateCampaignPayload): Promise<Campaign> =>
    apiClient.post<Campaign>('/campaigns', payload).then((r) => r.data),

  update: (id: string, payload: UpdateCampaignPayload): Promise<Campaign> =>
    apiClient.patch<Campaign>(`/campaigns/${id}`, payload).then((r) => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/campaigns/${id}`).then(() => undefined),

  addInvestigation: (id: string, payload: AddInvestigationPayload): Promise<void> =>
    apiClient
      .post(`/campaigns/${id}/investigations`, payload)
      .then(() => undefined),

  removeInvestigation: (id: string, invId: string): Promise<void> =>
    apiClient
      .delete(`/campaigns/${id}/investigations/${invId}`)
      .then(() => undefined),

  getGraph: (id: string): Promise<CampaignGraphResponse> =>
    apiClient.get<CampaignGraphResponse>(`/campaigns/${id}/graph`).then((r) => r.data),

  getSimilar: (id: string): Promise<SimilarCampaign[]> =>
    apiClient.get<SimilarCampaign[]>(`/campaigns/${id}/similar`).then((r) => r.data),
}
