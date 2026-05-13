import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scanLinkedInIntel, listLinkedInIntelScans, deleteLinkedInIntelScan } from "./api";

export const useScanLinkedInIntel = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ query, query_type }: { query: string; query_type: string }) =>
      scanLinkedInIntel(query, query_type),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["linkedin-intel-history"] }),
  });
};

export const useLinkedInIntelHistory = (page = 1, page_size = 20) =>
  useQuery({
    queryKey: ["linkedin-intel-history", page, page_size],
    queryFn: () => listLinkedInIntelScans(page, page_size),
  });

export const useDeleteLinkedInIntelScan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteLinkedInIntelScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["linkedin-intel-history"] }),
  });
};
