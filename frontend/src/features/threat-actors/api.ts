import { apiClient } from '@/shared/api/client'
import type { ThreatActor, ThreatActorFilters, ThreatActorProfile, CampaignSummary } from './types'

export const threatActorsApi = {
  list: (filters: ThreatActorFilters = {}): Promise<ThreatActor[]> => {
    const params: Record<string, string> = {}
    if (filters.motivation) params.motivation = filters.motivation
    if (filters.sophistication) params.sophistication = filters.sophistication
    if (filters.origin_country) params.origin_country = filters.origin_country
    if (filters.search) params.search = filters.search
    return apiClient
      .get<ThreatActor[]>('/threat-actors', { params })
      .then((r) => r.data)
  },

  get: (id: string): Promise<ThreatActor> =>
    apiClient.get<ThreatActor>(`/threat-actors/${id}`).then((r) => r.data),

  getProfile: (id: string): Promise<ThreatActorProfile> =>
    apiClient.get<ThreatActorProfile>(`/threat-actors/${id}/profile`).then((r) => r.data),

  getCampaigns: (id: string): Promise<CampaignSummary[]> =>
    apiClient.get<CampaignSummary[]>(`/threat-actors/${id}/campaigns`).then((r) => r.data),
}
