import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { CorrelationResult } from "./types";

export function useCorrelation() {
  return useMutation({
    mutationFn: async (inputs: string[]) => {
      const res = await apiClient.post<CorrelationResult>("/correlation/analyze", inputs);
      return res.data;
    },
  });
}
