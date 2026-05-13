import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAsnIntelScan, listAsnIntelScans, lookupAsnIntel } from "./api";

export function useAsnIntelLookup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (query: string) => lookupAsnIntel(query),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["asn-intel-history"] }),
  });
}

export function useAsnIntelHistory(page = 1, page_size = 20) {
  return useQuery({
    queryKey: ["asn-intel-history", page, page_size],
    queryFn: () => listAsnIntelScans(page, page_size),
  });
}

export function useDeleteAsnIntelScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAsnIntelScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["asn-intel-history"] }),
  });
}
