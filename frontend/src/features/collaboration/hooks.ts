import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { CollabSession, OnlineUser } from "./types";
import { toast } from "@/shared/components/Toast";

export function useCollabSessions() {
  return useQuery({
    queryKey: ["collab-sessions"],
    queryFn: async () => {
      const res = await apiClient.get<CollabSession[]>("/collaboration/sessions");
      return res.data;
    },
  });
}

export function useOnlineUsers() {
  return useQuery({
    queryKey: ["online-users"],
    queryFn: async () => {
      const res = await apiClient.get<{ users: OnlineUser[]; total_online: number }>(
        "/collaboration/online-users"
      );
      return res.data;
    },
    refetchInterval: 30000,
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      investigationId,
      name,
    }: {
      investigationId: string;
      name: string;
    }) => {
      const res = await apiClient.post<CollabSession>("/collaboration/sessions", null, {
        params: { investigation_id: investigationId, name },
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collab-sessions"] });
      toast.success("Collaboration session created");
    },
  });
}
