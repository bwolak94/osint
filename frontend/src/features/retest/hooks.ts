import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { RetestSession } from "./types";
import { toast } from "@/shared/components/Toast";

export function useRetestSessions() {
  return useQuery({
    queryKey: ["retest-sessions"],
    queryFn: async () => {
      const res = await apiClient.get<RetestSession[]>("/retest-engine/sessions");
      return res.data;
    },
  });
}

export function useCreateRetest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      engagement_id: string;
      finding_ids: string[];
    }) => {
      const res = await apiClient.post<RetestSession>(
        "/retest-engine/sessions",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retest-sessions"] });
      toast.success("Retest session created");
    },
  });
}

export function useRunAutomated() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const res = await apiClient.post<RetestSession>(
        `/retest-engine/sessions/${sessionId}/run-automated`
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["retest-sessions"] });
      toast.success("Automated retests complete");
    },
  });
}

export function useUpdateRetestItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      sessionId,
      itemId,
      status,
      notes,
    }: {
      sessionId: string;
      itemId: string;
      status: string;
      notes?: string;
    }) => {
      const res = await apiClient.patch<RetestSession>(
        `/retest-engine/sessions/${sessionId}/items/${itemId}`,
        null,
        { params: { status, notes } }
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["retest-sessions"] }),
  });
}
