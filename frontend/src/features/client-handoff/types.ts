export interface HandoffItem {
  type: string;
  title: string;
  description: string;
  size_mb: number;
  included: boolean;
}

export interface HandoffPackage {
  id: string;
  name: string;
  engagement_id: string;
  client_name: string;
  status: string;
  items: HandoffItem[];
  download_token: string | null;
  created_at: string;
  delivered_at: string | null;
  pgp_signed: boolean;
  checksum_sha256: string | null;
}

export interface CreateHandoffInput {
  name: string;
  engagement_id: string;
  client_name: string;
  include_items?: string[];
}
