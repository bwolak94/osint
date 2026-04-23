import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchInvestigationVersions,
  fetchInvestigationDiff,
  fetchMergeCandidates,
  mergeInvestigations,
} from './api';
import type { MergeRequest } from './types';

const QUERY_KEYS = {
  versions: (id: string) => ['investigation-versions', id] as const,
  diff: (id: string, vA: string, vB: string) =>
    ['investigation-diff', id, vA, vB] as const,
  mergeCandidates: (id: string) => ['merge-candidates', id] as const,
};

export function useInvestigationVersions(investigationId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.versions(investigationId),
    queryFn: () => fetchInvestigationVersions(investigationId),
    enabled: investigationId.trim().length > 0,
    select: (data) => data.versions,
  });
}

export function useInvestigationDiff(
  investigationId: string,
  versionA: string,
  versionB: string,
) {
  return useQuery({
    queryKey: QUERY_KEYS.diff(investigationId, versionA, versionB),
    queryFn: () => fetchInvestigationDiff(investigationId, versionA, versionB),
    enabled:
      investigationId.trim().length > 0 &&
      versionA.trim().length > 0 &&
      versionB.trim().length > 0,
  });
}

export function useMergeCandidates(investigationId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.mergeCandidates(investigationId),
    queryFn: () => fetchMergeCandidates(investigationId),
    enabled: investigationId.trim().length > 0,
  });
}

export function useMergeInvestigations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MergeRequest) => mergeInvestigations(payload),
    onSuccess: () => {
      // Invalidate investigation list so the merged result appears
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}
