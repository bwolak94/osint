import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { FootprintScore } from "./types";

export function useFootprintScore() {
  return useMutation({
    mutationFn: async (target: string) => {
      const res = await apiClient.get<FootprintScore>("/footprint/score", {
        params: { target },
      });
      return res.data;
    },
  });
}
