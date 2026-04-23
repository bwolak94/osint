import { apiClient } from '@/shared/api/client'
import type { ThreatActor, ThreatActorFilters } from './types'

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
}
