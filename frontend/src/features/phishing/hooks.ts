import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { PhishingCampaign, PhishingTemplate } from "./types";
import { toast } from "@/shared/components/Toast";

export function usePhishingTemplates() {
  return useQuery({
    queryKey: ["phishing-templates"],
    queryFn: async () => {
      const res = await apiClient.get<PhishingTemplate[]>(
        "/phishing-campaigns/templates"
      );
      return res.data;
    },
  });
}

export function usePhishingCampaigns() {
  return useQuery({
    queryKey: ["phishing-campaigns"],
    queryFn: async () => {
      const res = await apiClient.get<PhishingCampaign[]>(
        "/phishing-campaigns/campaigns"
      );
      return res.data;
    },
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      template_id: string;
      target_count: number;
      authorized_by: string;
      engagement_id: string;
    }) => {
      const res = await apiClient.post<PhishingCampaign>(
        "/phishing-campaigns/campaigns",
        data
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["phishing-campaigns"] });
      toast.success("Campaign created");
    },
    onError: () => toast.error("Failed to create campaign"),
  });
}

export function useLaunchCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await apiClient.post<PhishingCampaign>(
        `/phishing-campaigns/campaigns/${id}/launch`
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["phishing-campaigns"] });
      toast.success("Campaign launched");
    },
    onError: () => toast.error("Failed to launch campaign"),
  });
}
