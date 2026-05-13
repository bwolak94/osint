import apiClient from "@/shared/api/client";
import type { RansomwareTrackerResult } from "./types";

export async function searchRansomware(query: string): Promise<RansomwareTrackerResult> {
  const { data } = await apiClient.post<RansomwareTrackerResult>("/ransomware-tracker/", { query });
  return data;
}
