export interface NewsItem {
  id: string
  title: string
  url: string
  description: string
  published_at: string
  source_id: string
  source_name: string
  category: NewsCategory
  country_iso: string
  language: string
  weight: number
  image_url?: string
}

export type NewsCategory =
  | 'geopolitics'
  | 'military'
  | 'cyber'
  | 'economy'
  | 'climate'
  | 'disaster'
  | 'health'
  | 'energy'
  | 'tech'
  | 'social'

export interface PostItem {
  id: string
  title: string
  url: string
  description: string
  published_at: string
  source_id: string
  source_name: string
  display_name: string
  category: 'social'
  platform: 'x' | 'truthsocial'
  account_id: string
  country_iso: string
  language: string
  weight: number
  image_url?: string
}

export interface PostsResponse {
  items: PostItem[]
  total: number
  page: number
  page_size: number
  last_updated: string | null
  account_counts: Record<string, number>
}

export interface MapEventItem {
  id: string
  layer: string
  lat: number
  lng: number
  title: string
  severity: 'high' | 'medium' | 'low'
  timestamp: string
  source: string
}

export interface MapEventsResponse {
  events: MapEventItem[]
  total: number
  last_updated: string | null
  source_counts: Record<string, number>
}

export interface NewsResponse {
  items: NewsItem[]
  total: number
  page: number
  page_size: number
  category: NewsCategory | null
}

export interface CategoryInfo {
  category: NewsCategory
  feed_count: number
  item_count: number
}

export interface HealthKey {
  key: string
  fetched_at: string | null
  age_min: number | null
  max_stale_min: number
  status: 'OK' | 'STALE' | 'WARN' | 'EMPTY'
}

export interface HealthResponse {
  status: 'OK' | 'DEGRADED'
  keys: HealthKey[]
  last_aggregation: string | null
  items_fetched_last_run: number | null
}

export interface BootstrapResponse {
  news: {
    items: NewsItem[]
    total_cached: number
  }
  events: {
    items: MapEventItem[]
    total: number
    last_updated: string | null
  }
  categories: NewsCategory[]
  meta: {
    last_run?: string
    duration_s?: number
    feeds_total?: number
    items_fetched?: number
    items_stored?: number
  }
  generated_at: string
}

export interface ClusterResponse {
  clusters: NewsCluster[]
  status: string
  message?: string
}

export interface NewsCluster {
  id: string
  headline: string
  articles: NewsItem[]
  categories: NewsCategory[]
  countries: string[]
  score: number
  first_seen: string
  last_seen: string
}
