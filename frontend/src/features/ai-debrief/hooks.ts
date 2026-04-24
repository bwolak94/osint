import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { AiDebrief } from "./types";

export function useGenerateDebrief() {
  return useMutation({
    mutationFn: async ({
      engagementId,
      scope,
    }: {
      engagementId: string;
      scope?: string;
    }) => {
      const res = await apiClient.post<AiDebrief>("/ai-debrief/generate", null, {
        params: { engagement_id: engagementId, scope },
      });
      return res.data;
    },
  });
}
