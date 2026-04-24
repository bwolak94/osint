import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { Assessment, MethodologyStep } from "./types";
import { toast } from "@/shared/components/Toast";

export function useMethodologySteps() {
  return useQuery({
    queryKey: ["methodology-steps"],
    queryFn: async () => {
      const res = await apiClient.get<MethodologyStep[]>("/methodology/steps");
      return res.data;
    },
  });
}

export function useAssessments() {
  return useQuery({
    queryKey: ["assessments"],
    queryFn: async () => {
      const res = await apiClient.get<Assessment[]>("/methodology/assessments");
      return res.data;
    },
  });
}

export function useCreateAssessment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      methodology,
      engagementId,
    }: {
      name: string;
      methodology: string;
      engagementId: string;
    }) => {
      const res = await apiClient.post<Assessment>("/methodology/assessments", null, {
        params: { name, methodology, engagement_id: engagementId },
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
      toast.success("Assessment created");
    },
  });
}

export function useCompleteStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      assessmentId,
      stepId,
    }: {
      assessmentId: string;
      stepId: string;
    }) => {
      const res = await apiClient.post<Assessment>(
        `/methodology/assessments/${assessmentId}/complete-step`,
        null,
        { params: { step_id: stepId } }
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assessments"] }),
  });
}
