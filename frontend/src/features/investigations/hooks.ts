import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { Investigation, CreateInvestigationRequest } from "./types";
import type { PaginatedResponse } from "@/shared/types/api";

export function useInvestigations() {
  return useQuery({
    queryKey: ["investigations"],
    queryFn: async () => {
      const response =
        await apiClient.get<PaginatedResponse<Investigation>>(
          "/api/v1/investigations",
        );
      return response.data;
    },
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ["investigations", id],
    queryFn: async () => {
      const response = await apiClient.get<Investigation>(
        `/api/v1/investigations/${id}`,
      );
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateInvestigation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateInvestigationRequest) => {
      const response = await apiClient.post<Investigation>(
        "/api/v1/investigations",
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}
