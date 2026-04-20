export interface WigleNetwork {
  netid: string
  ssid: string | null
  encryption: string | null
  channel: number | null
  trilat: number | null
  trilong: number | null
  first_seen: string | null
  last_seen: string | null
  country: string | null
  region: string | null
  city: string | null
  maps_url: string | null
}

export interface WigleScan {
  id: string
  query: string
  query_type: string
  total_results: number
  results: WigleNetwork[]
  created_at: string
}

export interface WigleListResponse {
  items: WigleScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
