import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";

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
      const res = await apiClient.post<InvestigationStub>("/investigations/", data);
      return res.data;
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
