export interface MacLookup {
  id: string
  mac_address: string
  oui_prefix: string | null
  manufacturer: string | null
  manufacturer_country: string | null
  device_type: string | null
  is_private: boolean | null
  is_multicast: boolean | null
  raw_data: Record<string, string | boolean | null>
  created_at: string
}

export interface MacLookupListResponse {
  items: MacLookup[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
