export interface FediverseProfile {
  platform: string
  handle: string
  display_name: string | null
  bio: string | null
  followers: number | null
  following: number | null
  posts: number | null
  did: string | null
  instance: string | null
  avatar_url: string | null
  profile_url: string | null
  created_at: string | null
}

export interface FediverseScan {
  id: string
  query: string
  total_results: number
  platforms_searched: string[]
  results: FediverseProfile[]
  created_at: string
}

export interface FediverseListResponse {
  items: FediverseScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
