import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import type { HandoffPackage, CreateHandoffInput } from "./types";

export function useHandoffPackages() {
  return useQuery({
    queryKey: ["handoff-packages"],
    queryFn: async () => {
      const res = await apiClient.get<HandoffPackage[]>("/client-handoff/packages");
      return res.data;
    },
  });
}

export function useCreatePackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateHandoffInput) => {
      const res = await apiClient.post<HandoffPackage>("/client-handoff/packages", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handoff-packages"] });
      toast.success("Package created");
    },
    onError: () => toast.error("Failed to create package"),
  });
}

export function usePreparePackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (packageId: string) => {
      const res = await apiClient.post<HandoffPackage>(`/client-handoff/packages/${packageId}/prepare?sign_with_pgp=true`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handoff-packages"] });
      toast.success("Package prepared & signed");
    },
    onError: () => toast.error("Preparation failed"),
  });
}
