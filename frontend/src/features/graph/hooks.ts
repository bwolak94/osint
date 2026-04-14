import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { GraphData } from "./types";

export function useGraphData(investigationId: string) {
  return useQuery({
    queryKey: ["graph", investigationId],
    queryFn: async () => {
      const response = await apiClient.get<GraphData>(
        `/api/v1/investigations/${investigationId}/graph`,
      );
      return response.data;
    },
    enabled: !!investigationId,
  });
}
