import apiClient from "@/shared/api/client";
import type { SubdomainTakeoverListResponse, SubdomainTakeoverResult } from "./types";

export async function scanSubdomainTakeover(domain: string): Promise<SubdomainTakeoverResult> {
  const { data } = await apiClient.post<SubdomainTakeoverResult>("/subdomain-takeover/", { domain });
  return data;
}

export async function listSubdomainTakeoverScans(page = 1, page_size = 20): Promise<SubdomainTakeoverListResponse> {
  const { data } = await apiClient.get<SubdomainTakeoverListResponse>("/subdomain-takeover/", { params: { page, page_size } });
  return data;
}

export async function deleteSubdomainTakeoverScan(id: string): Promise<void> {
  await apiClient.delete(`/subdomain-takeover/${id}`);
}
