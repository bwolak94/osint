import { apiClient } from '@/shared/api/client';
import type {
  InvestigationVersionsResponse,
  InvestigationDiffResponse,
  MergeCandidate,
  MergeRequest,
  MergeResponse,
} from './types';

export async function fetchInvestigationVersions(
  investigationId: string,
): Promise<InvestigationVersionsResponse> {
  const { data } = await apiClient.get<InvestigationVersionsResponse>(
    `/investigations/${investigationId}/versions`,
  );
  return data;
}

export async function fetchInvestigationDiff(
  investigationId: string,
  versionA: string,
  versionB: string,
): Promise<InvestigationDiffResponse> {
  const { data } = await apiClient.get<InvestigationDiffResponse>(
    `/investigations/${investigationId}/diff`,
    { params: { version_a: versionA, version_b: versionB } },
  );
  return data;
}

export async function fetchMergeCandidates(
  investigationId: string,
): Promise<MergeCandidate[]> {
  const { data } = await apiClient.get<MergeCandidate[]>(
    `/investigations/${investigationId}/merge-candidates`,
  );
  return data;
}

export async function mergeInvestigations(
  payload: MergeRequest,
): Promise<MergeResponse> {
  const { data } = await apiClient.post<MergeResponse>(
    '/investigations/merge',
    payload,
  );
  return data;
}
