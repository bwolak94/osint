import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteSubdomainTakeoverScan, listSubdomainTakeoverScans, scanSubdomainTakeover } from "./api";

export function useSubdomainTakeover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) => scanSubdomainTakeover(domain),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["subdomain-takeover-history"] }),
  });
}

export function useSubdomainTakeoverHistory(page = 1, page_size = 20) {
  return useQuery({
    queryKey: ["subdomain-takeover-history", page, page_size],
    queryFn: () => listSubdomainTakeoverScans(page, page_size),
  });
}

export function useDeleteSubdomainTakeoverScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSubdomainTakeoverScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["subdomain-takeover-history"] }),
  });
}
