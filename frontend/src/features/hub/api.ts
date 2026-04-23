/**
 * Hub API — thin wrappers around the Hub endpoints.
 * All calls go through the shared Axios client with JWT auto-refresh.
 */

import apiClient from "@/shared/api/client";
import type {
  AgentRunRequest,
  AgentRunResponse,
  AgentStatusResponse,
  HitlApprovalRequest,
  HitlApprovalResponse,
  StoredNewsArticle,
  NewsRagResponse,
} from "./types";

interface SynergyDismissResponse {
  event_id: string;
  dismissed: boolean;
  message: string;
}

export async function runHubAgent(
  payload: AgentRunRequest,
): Promise<AgentRunResponse> {
  const { data } = await apiClient.post<AgentRunResponse>(
    "/hub/agent/run",
    payload,
  );
  return data;
}

export async function getTaskStatus(
  taskId: string,
): Promise<AgentStatusResponse> {
  const { data } = await apiClient.get<AgentStatusResponse>(
    `/hub/tasks/${taskId}`,
  );
  return data;
}

export async function approveHitl(
  taskId: string,
  payload: HitlApprovalRequest,
): Promise<HitlApprovalResponse> {
  const { data } = await apiClient.post<HitlApprovalResponse>(
    `/hub/tasks/${taskId}/approve`,
    payload,
  );
  return data;
}

export async function dismissSynergySignal(
  eventId: string,
  userId: string,
  reason = "user_dismissed",
): Promise<SynergyDismissResponse> {
  const { data } = await apiClient.post<SynergyDismissResponse>(
    `/hub/synergy/${eventId}/dismiss`,
    { user_id: userId, reason },
  );
  return data;
}

export async function approveSynergyChain(
  taskId: string,
): Promise<HitlApprovalResponse> {
  return approveHitl(taskId, { approved: true });
}

export async function getNewsFeed(params?: {
  limit?: number;
  offset?: number;
  tag?: string;
}): Promise<{ articles: StoredNewsArticle[]; total: number; offset: number }> {
  const sp = new URLSearchParams();
  if (params?.limit !== undefined) sp.set("limit", String(params.limit));
  if (params?.offset !== undefined) sp.set("offset", String(params.offset));
  if (params?.tag) sp.set("tag", params.tag);
  const qs = sp.toString();
  const { data } = await apiClient.get<{
    articles: StoredNewsArticle[];
    total: number;
    offset: number;
  }>(`/hub/news/articles${qs ? `?${qs}` : ""}`);
  return data;
}

export async function askNewsRag(body: {
  query: string;
  top_k?: number;
}): Promise<NewsRagResponse> {
  const { data } = await apiClient.post<NewsRagResponse>("/hub/news/ask", body);
  return data;
}
