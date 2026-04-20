import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

interface UserSettings {
  theme: string;
  language: string;
  date_format: string;
  timezone: string;
  email_on_scan_complete: boolean;
  email_on_new_findings: boolean;
  email_weekly_digest: boolean;
  default_scan_depth: number;
  default_enabled_scanners: string[];
  anonymize_exports: boolean;
  data_retention_days: number;
  has_api_key: boolean;
  api_key_prefix: string | null;
  marketing_consent: boolean;
}

export function useUserSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await apiClient.get<UserSettings>("/settings/me");
      return res.data;
    },
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<UserSettings>) => {
      const res = await apiClient.patch<UserSettings>("/settings/me", data);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useGenerateApiKey() {
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<{ key: string; prefix: string }>("/settings/me/api-key");
      return res.data;
    },
  });
}

export function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiClient.delete("/settings/me/api-key");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}
