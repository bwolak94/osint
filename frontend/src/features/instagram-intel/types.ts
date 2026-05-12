export type QueryType = 'username' | 'name' | 'id'

export interface InstagramProfile {
  user_id: string | null
  username: string | null
  full_name: string | null
  biography: string | null
  profile_pic_url: string | null
  profile_url: string | null
  follower_count: number | null
  following_count: number | null
  media_count: number | null
  is_verified: boolean
  is_private: boolean
  external_url: string | null
  category: string | null
  source: string
}

export interface InstagramIntelScan {
  id: string
  query: string
  query_type: QueryType
  total_results: number
  results: InstagramProfile[]
  created_at: string
}

export interface InstagramIntelListResponse {
  items: InstagramIntelScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
