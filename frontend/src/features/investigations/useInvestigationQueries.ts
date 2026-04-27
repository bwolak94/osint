import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { STALE_5M, STALE_1M } from "@/shared/api/queryConfig";

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
  raw_data: Record<string, unknown>;
  extracted_identifiers: string[];
}

export interface Identity {
  id: string;
  name: string;
  type: string;
  confidence: number;
  data: Record<string, unknown>;
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

export interface InvestigationSummary {
  investigation_id: string;
  summary: string;
  key_findings: string[];
  risk_indicators: string[];
  recommended_actions: string[];
  scan_recommendations: { type: string; values: string[]; scanner: string; reason: string }[];
  risk_score: number;
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
    staleTime: STALE_1M,
  });
}

export function useInvestigationsInfinite() {
  return useInfiniteQuery({
    queryKey: ["investigations-infinite"],
    queryFn: async ({ pageParam }: { pageParam: string | undefined }) => {
      const params = new URLSearchParams();
      if (pageParam) params.set("cursor", pageParam);
      const res = await apiClient.get<InvestigationListResponse>(`/investigations/?${params}`);
      return res.data;
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: STALE_1M,
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
    staleTime: STALE_5M,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 3000 : false),
  });
}

export function useInvestigationResults(id: string, isRunning: boolean = false) {
  return useQuery({
    queryKey: ["investigation-results", id],
    queryFn: async () => {
      const res = await apiClient.get<InvestigationResults>(`/investigations/${id}/results/`);
      return res.data;
    },
    enabled: !!id,
    staleTime: isRunning ? 0 : STALE_5M,
    refetchInterval: isRunning ? 5000 : false,
  });
}

export function useInvestigationSummary(id: string) {
  return useQuery({
    queryKey: ["investigation-summary", id],
    queryFn: async () => {
      const res = await apiClient.get<InvestigationSummary>(`/investigations/${id}/summarize`);
      return res.data;
    },
    enabled: !!id,
    staleTime: STALE_5M,
  });
}
