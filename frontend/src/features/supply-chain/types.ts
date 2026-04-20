export interface Cve {
  id: string | null
  summary: string
  severity: string
  published: string | null
}

export interface PackageResult {
  name: string
  registry: string
  version: string | null
  downloads: number | null
  maintainer_emails: string[]
  cves: Cve[]
  cve_count: number
  risk_score: string
}

export interface SupplyChainScan {
  id: string
  target: string
  target_type: string
  total_packages: number
  total_cves: number
  packages: PackageResult[]
  created_at: string
}

export interface SupplyChainListResponse {
  items: SupplyChainScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
