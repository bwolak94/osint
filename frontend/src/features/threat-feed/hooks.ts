import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import type { ThreatFeed, CreateFeedInput } from "./types";

export function useThreatFeeds() {
  return useQuery({
    queryKey: ["threat-feeds"],
    queryFn: async () => {
      const res = await apiClient.get<ThreatFeed[]>("/threat-feed/feeds");
      return res.data;
    },
  });
}

export function useCreateFeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateFeedInput) => {
      const res = await apiClient.post<ThreatFeed>("/threat-feed/feeds", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["threat-feeds"] });
      toast.success("Feed created");
    },
    onError: () => toast.error("Failed to create feed"),
  });
}

export function useExportFeed() {
  return useMutation({
    mutationFn: async ({ feedId, format }: { feedId: string; format: string }) => {
      const res = await apiClient.get<{ content?: string; indicators?: unknown[]; format: string; feed_name?: string }>(
        `/threat-feed/feeds/${feedId}/export?format=${format}`
      );
      return res.data;
    },
    onError: () => toast.error("Export failed"),
  });
}
