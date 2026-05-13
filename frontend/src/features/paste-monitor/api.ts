import apiClient from "@/shared/api/client";
import type { PasteMonitorResult } from "./types";

export async function searchPastes(query: string): Promise<PasteMonitorResult> {
  const { data } = await apiClient.post<PasteMonitorResult>("/paste-monitor/", { query });
  return data;
}
