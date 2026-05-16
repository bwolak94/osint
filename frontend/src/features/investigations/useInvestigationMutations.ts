import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { z } from "zod";
import { apiClient } from "@/shared/api/client";
import { validateResponse } from "@/shared/api/validateResponse";
import { toast } from "@/shared/components/Toast";
import type { Investigation } from "./useInvestigationQueries";

const InvestigationStubSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  status: z.string(),
});

function isInvestigation(obj: unknown): obj is Investigation {
  return typeof obj === "object" && obj !== null && "status" in obj && "id" in obj;
}

export interface CreateInvestigationInput {
  title: string;
  description?: string;
  seed_inputs: { type: string; value: string }[];
  tags: string[];
  enabled_scanners?: string[];
}

export interface InvestigationStub {
  id: string;
  title: string;
  status: string;
}

export type UseCreateInvestigationResult = UseMutationResult<
  InvestigationStub,
  Error,
  CreateInvestigationInput
>;
export type UseStartInvestigationResult = UseMutationResult<void, Error, string>;
export type UsePauseInvestigationResult = UseMutationResult<void, Error, string>;

export function useCreateInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateInvestigationInput) => {
      const res = await apiClient.post<unknown>("/investigations", data);
      return validateResponse(InvestigationStubSchema, res.data, "useCreateInvestigation");
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["investigations"] });
      void qc.invalidateQueries({ queryKey: ["investigations-infinite"] });
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
      await apiClient.post(`/investigations/${id}/start`);
    },
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ["investigation", id] });
      const prev = qc.getQueryData(["investigation", id]);
      qc.setQueryData(["investigation", id], (old: unknown) =>
        isInvestigation(old) ? { ...old, status: "running" } : old
      );
      return { prev };
    },
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: ["investigation", id] });
      void qc.invalidateQueries({ queryKey: ["investigation-results", id] });
      void qc.invalidateQueries({ queryKey: ["investigations"] });
      void qc.invalidateQueries({ queryKey: ["investigations-infinite"] });
      toast.success("Scan started");
    },
    onError: (_err, id, ctx) => {
      if (ctx?.prev) qc.setQueryData(["investigation", id], ctx.prev);
      toast.error("Failed to start scan");
    },
  });
}

export function usePauseInvestigation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/investigations/${id}/pause`);
    },
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ["investigation", id] });
      const prev = qc.getQueryData(["investigation", id]);
      qc.setQueryData(["investigation", id], (old: unknown) =>
        isInvestigation(old) ? { ...old, status: "paused" } : old
      );
      return { prev };
    },
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: ["investigation", id] });
    },
    onError: (_err, id, ctx) => {
      if (ctx?.prev) qc.setQueryData(["investigation", id], ctx.prev);
    },
  });
}
