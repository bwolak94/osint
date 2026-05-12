export type QueryType = 'name' | 'username' | 'id' | 'email' | 'phone'

export interface FacebookProfile {
  uid: string | null
  name: string | null
  username: string | null
  profile_url: string | null
  avatar_url: string | null
  cover_url: string | null
  bio: string | null
  location: string | null
  hometown: string | null
  work: string[]
  education: string[]
  followers: number | null
  friends: number | null
  public_posts: number | null
  verified: boolean
  category: string | null
  source: string
}

export interface FacebookIntelScan {
  id: string
  query: string
  query_type: QueryType
  total_results: number
  results: FacebookProfile[]
  created_at: string
}

export interface FacebookIntelListResponse {
  items: FacebookIntelScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
