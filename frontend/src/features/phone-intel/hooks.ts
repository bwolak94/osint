import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { PhoneIntelResult } from "./types";

export function usePhoneLookup() {
  return useMutation({
    mutationFn: async (phone: string) => {
      const res = await apiClient.get<PhoneIntelResult>("/phone-intel/lookup", { params: { phone } });
      return res.data;
    },
  });
}
