export type InvestigationStatus = "pending" | "in_progress" | "completed" | "failed";

export interface Identity {
  id: string;
  platform: string;
  username: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface Investigation {
  id: string;
  title: string;
  description: string;
  status: InvestigationStatus;
  identities: Identity[];
  created_at: string;
  updated_at: string;
}

export interface CreateInvestigationRequest {
  title: string;
  description: string;
}
