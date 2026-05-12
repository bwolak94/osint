import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { SlaMetrics } from "./types";

export function useSlaMetrics(engagementId?: string) {
  return useQuery({
    queryKey: ["sla-metrics", engagementId],
    queryFn: async () => {
      const res = await apiClient.get<SlaMetrics>("/sla/metrics", {
        params: engagementId ? { engagement_id: engagementId } : {},
      });
      return res.data;
    },
    refetchInterval: 60000,
  });
}
