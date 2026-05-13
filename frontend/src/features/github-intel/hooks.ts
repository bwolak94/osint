import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scanGitHubIntel, listGitHubIntelScans, deleteGitHubIntelScan } from "./api";

export const useScanGitHubIntel = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ query, query_type }: { query: string; query_type: string }) =>
      scanGitHubIntel(query, query_type),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["github-intel-history"] }),
  });
};

export const useGitHubIntelHistory = (page = 1, page_size = 20) =>
  useQuery({
    queryKey: ["github-intel-history", page, page_size],
    queryFn: () => listGitHubIntelScans(page, page_size),
  });

export const useDeleteGitHubIntelScan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteGitHubIntelScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["github-intel-history"] }),
  });
};
