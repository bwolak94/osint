import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";

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

export function useInvestigationResults(id: string, isRunning: boolean = false) {
  return useQuery({
    queryKey: ["investigation-results", id],
    queryFn: async () => {
      const res = await apiClient.get<InvestigationResults>(`/investigations/${id}/results/`);
      return res.data;
    },
    enabled: !!id,
    refetchInterval: isRunning ? 5000 : false,
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
      toast.success("Investigation created");
    },
    onError: (e: Error) => {
      toast.error(e.message ?? "Failed to create investigation");
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
      toast.success("Scan started");
    },
    onError: () => {
      toast.error("Failed to start scan");
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

export function useComments(investigationId: string) {
  return useQuery({
    queryKey: ["comments", investigationId],
    queryFn: async () => {
      const res = await apiClient.get(`/investigations/${investigationId}/comments`);
      return res.data;
    },
    enabled: !!investigationId,
  });
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

export function useInvestigationSummary(id: string) {
  return useQuery({
    queryKey: ["investigation-summary", id],
    queryFn: async () => {
      const res = await apiClient.get<InvestigationSummary>(`/investigations/${id}/summarize`);
      return res.data;
    },
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAddComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ investigationId, text }: { investigationId: string; text: string }) => {
      const res = await apiClient.post(`/investigations/${investigationId}/comments`, { text });
      return res.data;
    },
    onSuccess: (_, { investigationId }) => {
      qc.invalidateQueries({ queryKey: ["comments", investigationId] });
    },
  });
}
