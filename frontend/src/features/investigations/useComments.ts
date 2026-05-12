import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export function useComments(investigationId: string) {
  return useQuery({
    queryKey: ["comments", investigationId],
    queryFn: async () => {
      const res = await apiClient.get(`/investigations/${investigationId}/comments`);
      return res.data;
    },
    enabled: !!investigationId,
  });
}

export function useAddComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ investigationId, text }: { investigationId: string; text: string }) => {
      const res = await apiClient.post(`/investigations/${investigationId}/comments`, { text });
      return res.data;
    },
    onSuccess: (_, { investigationId }) => {
      qc.invalidateQueries({ queryKey: ["comments", investigationId] });
    },
  });
}
