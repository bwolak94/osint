import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { EvidenceItem, CreateEvidenceInput } from "./types";
import { toast } from "@/shared/components/Toast";

export function useEvidenceLocker(investigationId?: string) {
  return useQuery({
    queryKey: ["evidence-locker", investigationId],
    queryFn: async () => {
      const res = await apiClient.get<EvidenceItem[]>("/evidence-locker", {
        params: investigationId ? { investigation_id: investigationId } : {},
      });
      return res.data;
    },
  });
}

export function useCreateEvidenceLocker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateEvidenceInput) => {
      const res = await apiClient.post<EvidenceItem>("/evidence-locker", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evidence-locker"] });
      toast.success("Evidence logged");
    },
    onError: () => toast.error("Failed to log evidence"),
  });
}

export function useDeleteEvidenceLocker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/evidence-locker/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evidence-locker"] });
      toast.success("Evidence removed");
    },
  });
}
