import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { C2Framework } from "./types";

export function useC2Frameworks() {
  return useQuery({
    queryKey: ["c2-frameworks"],
    queryFn: async () => {
      const res = await apiClient.get<C2Framework[]>("/c2/frameworks");
      return res.data;
    },
  });
}
