import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { SocialGraphResult } from "./types";

export function useSocialGraphMap() {
  return useMutation({
    mutationFn: async ({ target, depth = 2 }: { target: string; depth?: number }) => {
      const res = await apiClient.get<SocialGraphResult>("/social-graph/map", { params: { target, depth } });
      return res.data;
    },
  });
}
