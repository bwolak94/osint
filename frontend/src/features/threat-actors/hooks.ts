import { useQuery } from '@tanstack/react-query'
import { threatActorsApi } from './api'
import type { ThreatActorFilters } from './types'

export function useThreatActorProfile(id: string) {
  return useQuery({
    queryKey: ['threat-actors', 'profile', id],
    queryFn: () => threatActorsApi.getProfile(id),
    enabled: Boolean(id),
    staleTime: 5 * 60_000,
  })
}

const KEY = 'threat-actors'

export function useThreatActors(filters: ThreatActorFilters = {}) {
  return useQuery({
    queryKey: [KEY, 'list', filters],
    queryFn: () => threatActorsApi.list(filters),
    staleTime: 60_000,
  })
}

export function useThreatActor(id: string) {
  return useQuery({
    queryKey: [KEY, 'detail', id],
    queryFn: () => threatActorsApi.get(id),
    enabled: Boolean(id),
    staleTime: 60_000,
  })
}
