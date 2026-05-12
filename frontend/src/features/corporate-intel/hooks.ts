import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { CorporateProfile } from "./types";

export function useCorporateProfile() {
  return useMutation({
    mutationFn: async ({ company, country = "US" }: { company: string; country?: string }) => {
      const res = await apiClient.get<CorporateProfile>("/corporate-intel/profile", { params: { company, country } });
      return res.data;
    },
  });
}
