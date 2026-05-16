import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiClient } from "@/shared/api/client";
import { validateResponse } from "@/shared/api/validateResponse";
import { STALE_5M, STALE_1M } from "@/shared/api/queryConfig";

// ---------------------------------------------------------------------------
// Zod schemas — catch backend API drift at runtime (#27, #33)
// ---------------------------------------------------------------------------

const SeedInputSchema = z.object({
  type: z.string(),
  value: z.string(),
});

const InvestigationSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  description: z.string().nullable(),
  status: z.string(),
  owner_id: z.string().uuid(),
  seed_inputs: z.array(SeedInputSchema),
  tags: z.array(z.string()),
  scan_progress: z
    .object({ completed: z.number(), total: z.number(), percentage: z.number() })
    .optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

const InvestigationListResponseSchema = z.object({
  items: z.array(InvestigationSchema),
  total: z.number(),
  has_next: z.boolean(),
  next_cursor: z.string().nullable(),
});

const ScanResultSchema = z.object({
  id: z.string().uuid(),
  scanner_name: z.string(),
  input_value: z.string(),
  status: z.string(),
  findings_count: z.number(),
  duration_ms: z.number(),
  created_at: z.string(),
  error_message: z.string().nullable(),
  raw_data: z.record(z.unknown()),
  extracted_identifiers: z.array(z.string()),
});

const IdentitySchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  type: z.string(),
  confidence: z.number(),
  data: z.record(z.unknown()),
  sources: z.array(z.string()),
});

const InvestigationResultsSchema = z.object({
  investigation_id: z.string().uuid(),
  scan_results: z.array(ScanResultSchema),
  total_scans: z.number(),
  successful_scans: z.number(),
  failed_scans: z.number(),
  identities: z.array(IdentitySchema),
});

const InvestigationSummarySchema = z.object({
  investigation_id: z.string().uuid(),
  summary: z.string(),
  key_findings: z.array(z.string()),
  risk_indicators: z.array(z.string()),
  recommended_actions: z.array(z.string()),
  scan_recommendations: z.array(
    z.object({
      type: z.string(),
      values: z.array(z.string()),
      scanner: z.string(),
      reason: z.string(),
    }),
  ),
  risk_score: z.number(),
});

// ---------------------------------------------------------------------------
// Inferred TypeScript types — single source of truth
// ---------------------------------------------------------------------------

export type Investigation = z.infer<typeof InvestigationSchema>;
export type ScanResult = z.infer<typeof ScanResultSchema>;
export type Identity = z.infer<typeof IdentitySchema>;
export type InvestigationResults = z.infer<typeof InvestigationResultsSchema>;
export type InvestigationSummary = z.infer<typeof InvestigationSummarySchema>;

type InvestigationListResponse = z.infer<typeof InvestigationListResponseSchema>;

// ---------------------------------------------------------------------------
// Query hooks — all fetch functions accept a signal for request cancellation
// ---------------------------------------------------------------------------

export function useInvestigations(cursor?: string) {
  return useQuery({
    queryKey: ["investigations", cursor],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams();
      if (cursor) params.set("cursor", cursor);
      const res = await apiClient.get<unknown>(`/investigations?${params}`, { signal });
      return validateResponse(InvestigationListResponseSchema, res.data, "useInvestigations");
    },
    staleTime: STALE_1M,
  });
}

export function useInvestigationsInfinite() {
  return useInfiniteQuery({
    queryKey: ["investigations-infinite"],
    queryFn: async ({ pageParam, signal }: { pageParam: string | undefined; signal: AbortSignal }) => {
      const params = new URLSearchParams();
      if (pageParam) params.set("cursor", pageParam);
      const res = await apiClient.get<unknown>(`/investigations?${params}`, { signal });
      return validateResponse(InvestigationListResponseSchema, res.data, "useInvestigationsInfinite");
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: STALE_1M,
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ["investigation", id],
    queryFn: async ({ signal }) => {
      const res = await apiClient.get<unknown>(`/investigations/${id}`, { signal });
      return validateResponse(InvestigationSchema, res.data, "useInvestigation");
    },
    enabled: !!id,
    staleTime: STALE_5M,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 3000 : false),
  });
}

export function useInvestigationResults(id: string, isRunning: boolean = false) {
  return useQuery({
    queryKey: ["investigation-results", id],
    queryFn: async ({ signal }) => {
      const res = await apiClient.get<unknown>(`/investigations/${id}/results`, { signal });
      return validateResponse(InvestigationResultsSchema, res.data, "useInvestigationResults");
    },
    enabled: !!id,
    staleTime: STALE_5M,
    refetchInterval: isRunning ? 5000 : false,
  });
}

export function useInvestigationSummary(id: string) {
  return useQuery({
    queryKey: ["investigation-summary", id],
    queryFn: async ({ signal }) => {
      const res = await apiClient.get<unknown>(`/investigations/${id}/summarize`, { signal });
      return validateResponse(InvestigationSummarySchema, res.data, "useInvestigationSummary");
    },
    enabled: !!id,
    staleTime: STALE_5M,
  });
}
