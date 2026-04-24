import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { Vulnerability } from "./types";
import { toast } from "@/shared/components/Toast";

export function useVulnerabilities(severity?: string, status?: string) {
  return useQuery({
    queryKey: ["vulnerabilities", severity, status],
    queryFn: async () => {
      const res = await apiClient.get<Vulnerability[]>("/vuln-management", {
        params: { severity: severity || undefined, status: status || undefined },
      });
      return res.data;
    },
  });
}

export function useUpdateVuln() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      status,
      assignee,
    }: {
      id: string;
      status?: string;
      assignee?: string;
    }) => {
      const res = await apiClient.patch<Vulnerability>(`/vuln-management/${id}`, {
        status,
        assignee,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vulnerabilities"] });
      toast.success("Vulnerability updated");
    },
  });
}
