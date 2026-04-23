/**
 * Hub feature — TypeScript types matching backend Pydantic schemas.
 * Keep in sync with backend/src/api/v1/hub/schemas.py
 */

export type HubModule = "news" | "calendar" | "tasks" | "knowledge" | "chat";

export type AgentStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_hitl";

// ── API request/response shapes ──────────────────────────────────────────────

export interface AgentRunRequest {
  query: string;
  module: HubModule;
  user_preferences?: Record<string, unknown>;
}

export interface AgentRunResponse {
  task_id: string;
  status: AgentStatus;
  stream_url: string;
}

export interface AgentStatusResponse {
  task_id: string;
  status: AgentStatus;
  result: string | null;
  result_metadata: Record<string, unknown>;
  thoughts: string[];
  error: string | null;
  synergy_chains?: SynergyChain[];
}

export interface HitlApprovalRequest {
  approved: boolean;
}

export interface HitlApprovalResponse {
  task_id: string;
  status: AgentStatus;
  message: string;
}

// ── Phase 3: Cross-module synergy types ──────────────────────────────────────

export interface TaskModificationProposal {
  proposal_id: string;
  task_id: string;
  task_title: string;
  field: string;
  current_value: unknown;
  proposed_value: unknown;
  reason: string;
}

export interface CalendarAdjustmentProposal {
  proposal_id: string;
  event_id: string | null;
  summary: string;
  proposed_reschedule: string | null;
  reason: string;
}

export interface SynergyChain {
  chain_id: string;
  event: {
    event_id: string;
    source_module: "news" | "tasks" | "calendar" | "knowledge";
    event_type: string;
    action_relevance_score: number;
    emitted_at: string;
  };
  news_headline: string;
  news_url: string | null;
  task_proposals: TaskModificationProposal[];
  calendar_proposals: CalendarAdjustmentProposal[];
  status: "pending" | "approved" | "dismissed";
}

// ── News feed types (RSS scraper + RAG chat) ──────────────────────────────────

export interface StoredNewsArticle {
  article_id: string;
  url: string;
  title: string;
  source_domain: string;
  published_at: string;
  credibility_score: number;
  action_relevance_score: number;
  tags: string[];
  image_url?: string;
  summary: string;
}

export interface NewsRagResponse {
  answer: string;
  sources: Array<{ title: string; url: string; source_domain: string }>;
}

// ── WebSocket event shapes ────────────────────────────────────────────────────

export type WsEventType =
  | "graph_start"
  | "graph_done"
  | "node_start"
  | "thought"
  | "status_update"
  | "synergy_chain"
  | "error";

export interface WsEvent {
  type: WsEventType;
  task_id?: string;
  node?: string;
  thought?: string;
  chunk?: string;
  status?: AgentStatus;
  message?: string;
  synergy_chain?: SynergyChain;
}

// ── Zustand store shape ───────────────────────────────────────────────────────

export interface HubAgentState {
  taskId: string | null;
  status: AgentStatus | "idle";
  thoughts: string[];
  result: string | null;
  resultMetadata: Record<string, unknown>;
  error: string | null;
  streamUrl: string | null;

  // Actions
  startTask: (taskId: string, streamUrl: string) => void;
  appendThought: (thought: string) => void;
  setStatus: (status: AgentStatus | "idle") => void;
  setResult: (result: string | null, error: string | null, resultMetadata?: Record<string, unknown>) => void;
  reset: () => void;
}
