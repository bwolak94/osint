import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { CertTransparencyResult } from "./types";

export function useCertSearch() {
  return useMutation({
    mutationFn: async (domain: string) => {
      const res = await apiClient.get<CertTransparencyResult>("/cert-transparency/search", { params: { domain } });
      return res.data;
    },
  });
}
