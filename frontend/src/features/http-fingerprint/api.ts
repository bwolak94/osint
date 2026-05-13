import apiClient from "@/shared/api/client";
import type { HttpFingerprintListResponse, HttpFingerprintResult } from "./types";

export async function fingerprintUrl(url: string): Promise<HttpFingerprintResult> {
  const { data } = await apiClient.post<HttpFingerprintResult>("/http-fingerprint/", { url });
  return data;
}

export async function listHttpFingerprintScans(page = 1, page_size = 20): Promise<HttpFingerprintListResponse> {
  const { data } = await apiClient.get<HttpFingerprintListResponse>("/http-fingerprint/", { params: { page, page_size } });
  return data;
}

export async function deleteHttpFingerprintScan(id: string): Promise<void> {
  await apiClient.delete(`/http-fingerprint/${id}`);
}
