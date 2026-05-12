export interface CanaryToken {
  id: string;
  name: string;
  type: string;
  token_url: string;
  status: string;
  trigger_count: number;
  last_triggered: string | null;
  deployment_notes: string;
  tags: string[];
  created_at: string;
}

export interface CanaryAlert {
  id: string;
  token_id: string;
  token_name: string;
  triggered_at: string;
  source_ip: string;
  user_agent: string | null;
  geo_location: string | null;
  additional_data: Record<string, unknown>;
}

export interface CreateTokenInput {
  name: string;
  type: string;
  deployment_notes?: string;
  tags?: string[];
}
