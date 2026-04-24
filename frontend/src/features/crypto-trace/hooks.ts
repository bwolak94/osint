import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { CryptoTraceResult } from "./types";

export function useCryptoTrace() {
  return useMutation({
    mutationFn: async ({ address, currency = "BTC" }: { address: string; currency?: string }) => {
      const res = await apiClient.get<CryptoTraceResult>("/crypto-trace/trace", { params: { address, currency } });
      return res.data;
    },
  });
}
