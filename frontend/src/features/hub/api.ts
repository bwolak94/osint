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
  ConversationRecord,
  NewsSource,
  NewsTopic,
  NewsBookmark,
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

export async function cancelTask(taskId: string): Promise<void> {
  await apiClient.delete(`/hub/tasks/${taskId}`);
}

export async function getConversations(params?: {
  limit?: number;
  offset?: number;
  module?: string;
}): Promise<{ conversations: ConversationRecord[]; total: number; offset: number }> {
  const sp = new URLSearchParams();
  if (params?.limit !== undefined) sp.set("limit", String(params.limit));
  if (params?.offset !== undefined) sp.set("offset", String(params.offset));
  if (params?.module) sp.set("module", params.module);
  const qs = sp.toString();
  const { data } = await apiClient.get<{ conversations: ConversationRecord[]; total: number; offset: number }>(
    `/hub/conversations${qs ? `?${qs}` : ""}`,
  );
  return data;
}

export async function getNewsSources(): Promise<NewsSource[]> {
  const { data } = await apiClient.get<{ sources: NewsSource[] }>("/hub/news/sources");
  return data.sources;
}

export async function addNewsSource(source: { url: string; name: string }): Promise<NewsSource> {
  const { data } = await apiClient.post<NewsSource>("/hub/news/sources", source);
  return data;
}

export async function removeNewsSource(sourceUrl: string): Promise<void> {
  await apiClient.delete(`/hub/news/sources?url=${encodeURIComponent(sourceUrl)}`);
}

export async function getNewsTopics(): Promise<NewsTopic> {
  const { data } = await apiClient.get<NewsTopic>("/hub/news/topics");
  return data;
}

export async function updateNewsTopics(topics: string[]): Promise<NewsTopic> {
  const { data } = await apiClient.put<NewsTopic>("/hub/news/topics", { topics });
  return data;
}

export async function getNewsBookmarks(): Promise<NewsBookmark[]> {
  const { data } = await apiClient.get<{ bookmarks: NewsBookmark[] }>("/hub/news/bookmarks");
  return data.bookmarks;
}

export async function addNewsBookmark(
  articleId: string,
  extra?: { url?: string; title?: string; source_domain?: string },
): Promise<NewsBookmark> {
  const { data } = await apiClient.post<NewsBookmark>("/hub/news/bookmarks", {
    article_id: articleId,
    ...extra,
  });
  return data;
}

export async function removeNewsBookmark(articleId: string): Promise<void> {
  await apiClient.delete(`/hub/news/bookmarks/${articleId}`);
}

export async function getNewsTrending(): Promise<{ trending: Array<{ tag: string; count: number }> }> {
  const { data } = await apiClient.get<{ trending: Array<{ tag: string; count: number }> }>("/hub/news/trending");
  return data;
}

export async function triggerNewsScrape(): Promise<{ status: string; task_id: string }> {
  const { data } = await apiClient.post<{ status: string; task_id: string }>("/hub/news/scrape/trigger");
  return data;
}

export async function getQueueStatus(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<Record<string, unknown>>("/hub/queue/status");
  return data;
}
