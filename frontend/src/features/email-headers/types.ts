export interface Hop {
  index: number
  from_host: string | null
  by_host: string | null
  ip: string | null
  timestamp: string | null
  protocol: string | null
  delay_seconds: number | null
}

export interface EmailHeaderCheck {
  id: string
  subject: string | null
  sender_from: string | null
  sender_reply_to: string | null
  originating_ip: string | null
  originating_country: string | null
  originating_city: string | null
  spf_result: string | null
  dkim_result: string | null
  dmarc_result: string | null
  is_spoofed: boolean
  hops: Hop[]
  raw_headers_summary: Record<string, string>
  created_at: string
}

export interface EmailHeaderListResponse {
  items: EmailHeaderCheck[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
