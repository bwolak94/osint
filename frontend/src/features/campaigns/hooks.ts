import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { campaignsApi } from './api'
import type {
  CreateCampaignPayload,
  UpdateCampaignPayload,
  AddInvestigationPayload,
} from './types'

const CAMPAIGNS_KEY = 'campaigns'

export function useCampaigns(skip = 0, limit = 20) {
  return useQuery({
    queryKey: [CAMPAIGNS_KEY, { skip, limit }],
    queryFn: () => campaignsApi.list(skip, limit),
  })
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: [CAMPAIGNS_KEY, id],
    queryFn: () => campaignsApi.get(id),
    enabled: Boolean(id),
  })
}

export function useCampaignGraph(id: string, enabled: boolean) {
  return useQuery({
    queryKey: [CAMPAIGNS_KEY, id, 'graph'],
    queryFn: () => campaignsApi.getGraph(id),
    enabled: enabled && Boolean(id),
  })
}

export function useSimilarCampaigns(id: string, enabled: boolean) {
  return useQuery({
    queryKey: [CAMPAIGNS_KEY, id, 'similar'],
    queryFn: () => campaignsApi.getSimilar(id),
    enabled: enabled && Boolean(id),
  })
}

export function useCreateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateCampaignPayload) => campaignsApi.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY] })
    },
  })
}

export function useUpdateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCampaignPayload }) =>
      campaignsApi.update(id, payload),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY] })
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY, id] })
    },
  })
}

export function useDeleteCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => campaignsApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY] })
    },
  })
}

export function useAddInvestigation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AddInvestigationPayload }) =>
      campaignsApi.addInvestigation(id, payload),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY, id] })
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY] })
    },
  })
}

export function useRemoveInvestigation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, invId }: { id: string; invId: string }) =>
      campaignsApi.removeInvestigation(id, invId),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY, id] })
      void qc.invalidateQueries({ queryKey: [CAMPAIGNS_KEY] })
    },
  })
}
