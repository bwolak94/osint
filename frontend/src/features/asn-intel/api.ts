import apiClient from "@/shared/api/client";
import type { AsnIntelListResponse, AsnIntelResult } from "./types";

export async function lookupAsnIntel(query: string): Promise<AsnIntelResult> {
  const { data } = await apiClient.post<AsnIntelResult>("/asn-intel/", { query });
  return data;
}

export async function listAsnIntelScans(page = 1, page_size = 20): Promise<AsnIntelListResponse> {
  const { data } = await apiClient.get<AsnIntelListResponse>("/asn-intel/", { params: { page, page_size } });
  return data;
}

export async function deleteAsnIntelScan(id: string): Promise<void> {
  await apiClient.delete(`/asn-intel/${id}`);
}
