export interface GhRepo {
  name: string;
  description: string | null;
  stars: number;
  forks: number;
  language: string | null;
  url: string;
  is_fork: boolean;
  topics: string[];
}

export interface GitHubProfile {
  user_id: number | null;
  username: string | null;
  full_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  profile_url: string | null;
  company: string | null;
  blog: string | null;
  location: string | null;
  email: string | null;
  twitter_username: string | null;
  followers: number | null;
  following: number | null;
  public_repos: number | null;
  public_gists: number | null;
  created_at: string | null;
  is_verified: boolean;
  account_type: string;
  top_repos: GhRepo[];
  languages: string[];
  emails_in_commits: string[];
  source: string;
}

export interface GitHubIntelScan {
  id: string;
  query: string;
  query_type: string;
  total_results: number;
  results: GitHubProfile[];
  created_at: string;
}

export interface GitHubIntelListResponse {
  items: GitHubIntelScan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
