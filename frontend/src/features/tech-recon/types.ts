export interface ModuleResultData {
  found: boolean
  data?: Record<string, unknown>
  error?: string | null
  status?: string
  skipped?: boolean
  reason?: string
}

export interface TechReconScan {
  id: string
  target: string
  target_type: 'domain' | 'ip'
  modules_run: string[]
  results: Record<string, ModuleResultData>
  created_at: string
}

export interface TechReconListResponse {
  items: TechReconScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TechReconRequest {
  target: string
  modules?: string[]
}

export interface ModuleGroup {
  key: string
  label: string
  modules: string[]
}

export const MODULE_GROUPS: ModuleGroup[] = [
  {
    key: 'dns',
    label: 'DNS & Subdomains',
    modules: ['dns_lookup', 'dns_bruteforce', 'dnsdumpster', 'dnsx', 'subdomain_takeover'],
  },
  {
    key: 'ports',
    label: 'Ports & Banners',
    modules: ['internetdb', 'banner_grabber'],
  },
  {
    key: 'ssl',
    label: 'SSL & Security',
    modules: ['cert_transparency', 'common_files'],
  },
  {
    key: 'waf',
    label: 'WAF & HTTP',
    modules: ['waf_detect', 'httpx_probe'],
  },
  {
    key: 'bgp',
    label: 'BGP & ASN / Email',
    modules: ['bgp_hijack', 'asn_lookup', 'shared_hosting', 'mx_spf_dmarc', 'ipv6_mapper'],
  },
  {
    key: 'historical',
    label: 'Historical & Cloud',
    modules: ['traceroute', 'cloud_assets', 'wayback'],
  },
]

export const MODULE_LABELS: Record<string, string> = {
  dns_lookup: 'DNS Lookup',
  dns_bruteforce: 'DNS Bruteforce',
  dnsdumpster: 'DNS Dumpster',
  dnsx: 'DNSx',
  subdomain_takeover: 'Subdomain Takeover',
  internetdb: 'InternetDB (Ports)',
  banner_grabber: 'Banner Grabber',
  cert_transparency: 'SSL/TLS (CT Logs)',
  common_files: 'Common Files',
  waf_detect: 'WAF Detection',
  httpx_probe: 'HTTP Probe',
  bgp_hijack: 'BGP Route Miner',
  asn_lookup: 'ASN Mapping',
  shared_hosting: 'Shared Hosting',
  mx_spf_dmarc: 'MX / SPF / DMARC',
  ipv6_mapper: 'IPv6 Mapper',
  traceroute: 'Traceroute',
  cloud_assets: 'Cloud Buckets',
  wayback: 'Internet Archive',
}
