import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { ClientPortal } from "./types";
import { toast } from "@/shared/components/Toast";

export function useClientPortals() {
  return useQuery({
    queryKey: ["client-portals"],
    queryFn: async () => {
      const res = await apiClient.get<ClientPortal[]>(
        "/client-portal/portals"
      );
      return res.data;
    },
  });
}

export function useCreatePortal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      client_name: string;
      engagement_id: string;
      allowed_sections: string[];
    }) => {
      const res = await apiClient.post<ClientPortal>(
        "/client-portal/portals",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-portals"] });
      toast.success("Client portal created");
    },
  });
}

export function useInviteClient() {
  return useMutation({
    mutationFn: async ({
      portalId,
      email,
    }: {
      portalId: string;
      email: string;
    }) => {
      const res = await apiClient.post(
        `/client-portal/portals/${portalId}/invite`,
        null,
        { params: { email } }
      );
      return res.data;
    },
    onSuccess: () => toast.success("Invitation sent"),
  });
}
