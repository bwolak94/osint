import apiClient from "@/shared/api/client";
import type { LinkedInIntelScan, LinkedInIntelListResponse } from "./types";

export const scanLinkedInIntel = (query: string, query_type: string): Promise<LinkedInIntelScan> =>
  apiClient.post<LinkedInIntelScan>("/linkedin-intel/", { query, query_type }).then((r) => r.data);

export const listLinkedInIntelScans = (page = 1, page_size = 20): Promise<LinkedInIntelListResponse> =>
  apiClient
    .get<LinkedInIntelListResponse>("/linkedin-intel/", { params: { page, page_size } })
    .then((r) => r.data);

export const deleteLinkedInIntelScan = (id: string): Promise<void> =>
  apiClient.delete(`/linkedin-intel/${id}`).then(() => undefined);
