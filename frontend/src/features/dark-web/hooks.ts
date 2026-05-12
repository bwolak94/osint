import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { DarkWebScanResult } from "./types";

export function useDarkWebScan() {
  return useMutation({
    mutationFn: async ({
      query,
      daysBack = 30,
    }: {
      query: string;
      daysBack?: number;
    }) => {
      const res = await apiClient.get<DarkWebScanResult>("/dark-web/scan", {
        params: { query, days_back: daysBack },
      });
      return res.data;
    },
  });
}
