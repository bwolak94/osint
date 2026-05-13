import apiClient from "@/shared/api/client";
import type { GitHubIntelScan, GitHubIntelListResponse } from "./types";

export const scanGitHubIntel = (query: string, query_type: string): Promise<GitHubIntelScan> =>
  apiClient.post<GitHubIntelScan>("/github-intel/", { query, query_type }).then((r) => r.data);

export const listGitHubIntelScans = (page = 1, page_size = 20): Promise<GitHubIntelListResponse> =>
  apiClient
    .get<GitHubIntelListResponse>("/github-intel/", { params: { page, page_size } })
    .then((r) => r.data);

export const deleteGitHubIntelScan = (id: string): Promise<void> =>
  apiClient.delete(`/github-intel/${id}`).then(() => undefined);
