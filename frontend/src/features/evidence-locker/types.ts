export interface EvidenceItem {
  id: string;
  title: string;
  type: "screenshot" | "document" | "url" | "note" | "artifact" | "log";
  description: string;
  investigation_id: string | null;
  tags: string[];
  chain_of_custody: Array<{ action: string; timestamp: string; user: string; notes: string }>;
  hash_sha256: string | null;
  size_bytes: number | null;
  created_at: string;
  created_by: string;
  is_admissible: boolean;
}

export interface CreateEvidenceInput {
  title: string;
  type: string;
  description: string;
  investigation_id?: string;
  tags: string[];
  hash_sha256?: string;
}
