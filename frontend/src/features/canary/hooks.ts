import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import type { CanaryToken, CanaryAlert, CreateTokenInput } from "./types";

export function useCanaryTokens() {
  return useQuery({
    queryKey: ["canary-tokens"],
    queryFn: async () => {
      const res = await apiClient.get<CanaryToken[]>("/canary/tokens");
      return res.data;
    },
  });
}

export function useCanaryAlerts() {
  return useQuery({
    queryKey: ["canary-alerts"],
    queryFn: async () => {
      const res = await apiClient.get<CanaryAlert[]>("/canary/alerts");
      return res.data;
    },
    refetchInterval: 10000,
  });
}

export function useCreateToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateTokenInput) => {
      const res = await apiClient.post<CanaryToken>("/canary/tokens", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["canary-tokens"] });
      toast.success("Canary token deployed");
    },
    onError: () => toast.error("Failed to create token"),
  });
}

export function useTriggerToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (tokenId: string) => {
      const res = await apiClient.post<{ triggered: boolean; alert: CanaryAlert }>(`/canary/tokens/${tokenId}/trigger`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["canary-tokens"] });
      qc.invalidateQueries({ queryKey: ["canary-alerts"] });
      toast.success("Token triggered (test)");
    },
  });
}
