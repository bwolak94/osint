import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { TimeEntry } from "./types";
import { toast } from "@/shared/components/Toast";

export function useTimeEntries(engagementId?: string) {
  return useQuery({
    queryKey: ["time-entries", engagementId],
    queryFn: async () => {
      const res = await apiClient.get<TimeEntry[]>("/time-tracking/entries", {
        params: engagementId ? { engagement_id: engagementId } : {},
      });
      return res.data;
    },
  });
}

export function useTimeSummary(engagementId?: string) {
  return useQuery({
    queryKey: ["time-summary", engagementId],
    queryFn: async () => {
      const res = await apiClient.get<{
        total_hours: number;
        total_amount: number;
        billable_entries: number;
        by_category: Record<string, { minutes: number; amount: number }>;
      }>("/time-tracking/summary", {
        params: engagementId ? { engagement_id: engagementId } : {},
      });
      return res.data;
    },
  });
}

export function useStartTimer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      engagement_id: string;
      category: string;
      description: string;
      billable?: boolean;
      hourly_rate?: number;
    }) => {
      const res = await apiClient.post<TimeEntry>("/time-tracking/start", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-entries"] });
      toast.success("Timer started");
    },
  });
}

export function useStopTimer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<TimeEntry>("/time-tracking/stop");
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-entries", "time-summary"] });
      toast.success("Timer stopped");
    },
  });
}

export function useAddManual() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      engagement_id: string;
      category: string;
      description: string;
      duration_minutes: number;
      billable?: boolean;
      hourly_rate?: number;
    }) => {
      const res = await apiClient.post<TimeEntry>("/time-tracking/manual", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-entries", "time-summary"] });
      toast.success("Time entry added");
    },
  });
}
