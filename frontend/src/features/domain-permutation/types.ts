export interface PermutationItem {
  fuzzer: string
  domain: string
  registered: boolean
  dns_a: string[]
  dns_mx: string[]
}

export interface DomainPermutationScan {
  id: string
  target_domain: string
  total_permutations: number
  registered_count: number
  permutations: PermutationItem[]
  created_at: string
}

export interface DomainPermutationListResponse {
  items: DomainPermutationScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
