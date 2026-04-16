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

export interface ScanResult {
  id: string;
  scanner_name: string;
  input_value: string;
  status: string;
  findings_count: number;
  duration_ms: number;
  created_at: string;
  error_message: string | null;
  raw_data: Record<string, any>;
  extracted_identifiers: string[];
}

export interface Identity {
  id: string;
  name: string;
  type: string;
  confidence: number;
  data: Record<string, any>;
  sources: string[];
}

export interface InvestigationResults {
  investigation_id: string;
  scan_results: ScanResult[];
  total_scans: number;
  successful_scans: number;
  failed_scans: number;
  identities: Identity[];
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
      const res = await apiClient.get<Investigation>(`/investigations/${id}/`);
      return res.data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll every 3s while investigation is running
      return query.state.data?.status === "running" ? 3000 : false;
    },
  });
}

export function useInvestigationResults(id: string) {
  return useQuery({
    queryKey: ["investigation-results", id],
    queryFn: async () => {
      const res = await apiClient.get<InvestigationResults>(`/investigations/${id}/results/`);
      return res.data;
    },
    enabled: !!id,
    // Refetch periodically while we might still be getting new results
    refetchInterval: (query) => {
      // Keep polling if total_scans is 0 (scans may still be running)
      const data = query.state.data as InvestigationResults | undefined;
      if (!data || data.total_scans === 0) return 5000;
      return false;
    },
  });
}

interface CreateInvestigationInput {
  title: string;
  description?: string;
  seed_inputs: { type: string; value: string }[];
  tags: string[];
  enabled_scanners?: string[];
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
      await apiClient.post(`/investigations/${id}/start/`);
    },
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
      qc.invalidateQueries({ queryKey: ["investigation-results", id] });
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function usePauseInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/investigations/${id}/pause/`);
    },
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
    },
  });
}
