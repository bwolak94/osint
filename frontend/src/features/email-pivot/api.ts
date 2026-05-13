import apiClient from "@/shared/api/client";
import type { EmailPivotResult } from "./types";

export async function pivotEmail(email: string, hibpKey = ""): Promise<EmailPivotResult> {
  const { data } = await apiClient.post<EmailPivotResult>("/email-pivot/", { email, hibp_key: hibpKey });
  return data;
}
