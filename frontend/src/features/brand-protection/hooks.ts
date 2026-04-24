import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { BrandProtectionResult } from "./types";

export function useBrandScan() {
  return useMutation({
    mutationFn: async (brand: string) => {
      const res = await apiClient.get<BrandProtectionResult>("/brand-protection/scan", { params: { brand } });
      return res.data;
    },
  });
}
