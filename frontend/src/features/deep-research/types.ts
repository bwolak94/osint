export interface DeepResearchRequest {
  first_name?: string
  last_name?: string
  email?: string
  username?: string
  phone?: string
  nip?: string
  company_name?: string
}

export interface SocialProfile {
  platform: string
  url: string | null
  found: boolean
  username: string | null
  followers: number | null
  bio: string | null
}

export interface SocmintResult {
  profiles_found: number
  platforms_checked: number
  social_profiles: SocialProfile[]
  username_variations: string[]
}

export interface EmailIntelResult {
  email: string
  is_valid: boolean
  is_disposable: boolean
  breach_count: number
  breach_sources: string[]
  registered_services: string[]
  holehe_hits: string[]
}

export interface PhoneIntelResult {
  phone: string
  country: string
  carrier: string
  line_type: string
  is_valid: boolean
  spam_score: number
  breach_count: number
  associated_services: string[]
}

export interface KrsRecord {
  krs_number: string | null
  nip: string | null
  regon: string | null
  company_name: string
  status: string
  registration_date: string | null
  address: string | null
  board_members: string[]
  share_capital: string | null
}

export interface CorporateResult {
  krs_records: KrsRecord[]
  ceidg_found: boolean
  regon_data: Record<string, string> | null
  company_name: string | null
  related_entities: string[]
}

export interface DarkWebResult {
  leaks_found: number
  paste_hits: number
  forum_mentions: number
  marketplaces_seen: string[]
  sample_records: Record<string, string>[]
}

export interface RelationEdge {
  source: string
  target: string
  relation: string
  confidence: number
}

export interface RelationsGraph {
  nodes: Array<{ id: string; label: string; type: string }>
  edges: RelationEdge[]
}

export interface AiSynthesis {
  summary: string
  key_findings: string[]
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  confidence: number
  recommended_pivots: string[]
}

export interface DeepResearchResult {
  request_id: string
  target_label: string
  socmint: SocmintResult | null
  email_intel: EmailIntelResult | null
  phone_intel: PhoneIntelResult | null
  corporate: CorporateResult | null
  dark_web: DarkWebResult | null
  relations_graph: RelationsGraph
  ai_synthesis: AiSynthesis
  modules_run: string[]
  total_findings: number
}
