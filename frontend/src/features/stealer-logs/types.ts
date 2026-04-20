export interface Infection {
  source: string
  stealer_family: string | null
  date_compromised: string | null
  computer_name: string | null
  operating_system: string | null
  ip: string | null
  country: string | null
  credentials_count: number
  cookies_count: number
  autofill_count: number
  has_crypto_wallet: boolean
  risk_level: string
  raw: Record<string, unknown>
  error?: string
}

export interface StealerLogCheck {
  id: string
  query: string
  query_type: string
  total_infections: number
  infections: Infection[]
  sources_checked: string[]
  created_at: string
}

export interface StealerLogListResponse {
  items: StealerLogCheck[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
