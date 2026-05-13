export interface LinkedInProfile {
  username: string | null;
  full_name: string | null;
  headline: string | null;
  location: string | null;
  profile_pic_url: string | null;
  profile_url: string | null;
  connections: string | null;
  company: string | null;
  school: string | null;
  source: string;
}

export interface LinkedInIntelScan {
  id: string;
  query: string;
  query_type: string;
  total_results: number;
  results: LinkedInProfile[];
  created_at: string;
}

export interface LinkedInIntelListResponse {
  items: LinkedInIntelScan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
