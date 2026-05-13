export interface SubdomainResult {
  subdomain: string;
  cname: string | null;
  vulnerable_service: string | null;
  risk: string;
  resolves: boolean;
  note: string | null;
}

export interface SubdomainTakeoverResult {
  id: string | null;
  created_at: string | null;
  domain: string;
  total_subdomains: number;
  vulnerable: SubdomainResult[];
  safe: SubdomainResult[];
}

export interface SubdomainTakeoverListResponse {
  items: SubdomainTakeoverResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
