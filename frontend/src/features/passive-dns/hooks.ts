import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { PassiveDnsResult } from "./types";

export function usePassiveDnsLookup() {
  return useMutation({
    mutationFn: async ({
      query,
      recordType,
    }: {
      query: string;
      recordType?: string;
    }) => {
      const res = await apiClient.get<PassiveDnsResult>("/passive-dns/lookup", {
        params: { query, record_type: recordType },
      });
      return res.data;
    },
  });
}
