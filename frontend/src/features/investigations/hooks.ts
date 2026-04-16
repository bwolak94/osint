import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface Investigation {
  id: string;
  title: string;
  description: string;
  status: string;
  owner_id: string;
  seed_inputs: { type: string; value: string }[];
  tags: string[];
  scan_progress?: { completed: number; total: number; percentage: number };
  created_at: string;
  updated_at: string;
}

interface InvestigationListResponse {
  items: Investigation[];
  total: number;
  has_next: boolean;
  next_cursor: string | null;
}

export function useInvestigations(cursor?: string) {
  return useQuery({
    queryKey: ["investigations", cursor],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      const res = await apiClient.get<InvestigationListResponse>(`/investigations/?${params}`);
      return res.data;
    },
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ["investigation", id],
    queryFn: async () => {
      const res = await apiClient.get<Investigation>(`/investigations/${id}`);
      return res.data;
    },
    enabled: !!id,
  });
}

export function useInvestigationResults(id: string) {
  return useQuery({
    queryKey: ["investigation-results", id],
    queryFn: async () => {
      const res = await apiClient.get(`/investigations/${id}/results`);
      return res.data;
    },
    enabled: !!id,
  });
}

interface CreateInvestigationInput {
  title: string;
  description?: string;
  seed_inputs: { type: string; value: string }[];
  tags: string[];
}

export function useCreateInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateInvestigationInput) => {
      const res = await apiClient.post<Investigation>("/investigations/", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function useStartInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/investigations/${id}/start`);
    },
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function usePauseInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/investigations/${id}/pause`);
    },
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
    },
  });
}
