export interface ClientPortal {
  id: string;
  name: string;
  client_name: string;
  engagement_id: string;
  status: string;
  access_token: string;
  allowed_sections: string[];
  created_at: string;
  expires_at: string | null;
  view_count: number;
}
