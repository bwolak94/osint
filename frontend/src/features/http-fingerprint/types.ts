export interface SecurityScore {
  present: string[];
  missing: string[];
  score: number;
}

export interface HttpFingerprintResult {
  id: string | null;
  created_at: string | null;
  url: string;
  final_url: string | null;
  status_code: number | null;
  technologies: string[];
  headers: Record<string, string>;
  security: SecurityScore;
  cdn: string | null;
  ip: string | null;
  error: string | null;
}

export interface HttpFingerprintListResponse {
  items: HttpFingerprintResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
