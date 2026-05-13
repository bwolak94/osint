import apiClient from "@/shared/api/client";
import type { UsernameScanResult } from "./types";

export async function scanUsername(username: string): Promise<UsernameScanResult> {
  const { data } = await apiClient.post<UsernameScanResult>("/username-scanner/", { username });
  return data;
}
