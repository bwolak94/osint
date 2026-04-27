export interface ThreatActor {
  id: string
  name: string
  aliases: string[]
  origin_country: string | null
  motivation: ThreatActorMotivation
  sophistication: ThreatActorSophistication
  active_since: string | null
  last_seen: string | null
  description: string
  ttps: string[]
  targets: string[]
  infrastructure: string[]
  malware_families: string[]
  cve_exploits: string[]
  ioc_count: number
  source: ThreatActorSource
  confidence: number
}

export type ThreatActorMotivation = 'financial' | 'espionage' | 'hacktivism' | 'sabotage'

export type ThreatActorSophistication = 'low' | 'medium' | 'high' | 'nation-state'

export type ThreatActorSource = 'threatfox' | 'otx' | 'manual'

export interface ThreatActorFilters {
  motivation?: ThreatActorMotivation | ''
  sophistication?: ThreatActorSophistication | ''
  origin_country?: string
  search?: string
}

export interface TacticCoverage {
  tactic: string
  techniques: string[]
  coverage_count: number
}

export interface CampaignSummary {
  id: string
  name: string
  year: number
  targets: string[]
  severity: 'critical' | 'high' | 'medium' | 'low'
}

export interface IOCCategory {
  category: string
  count: number
  samples: string[]
}

export interface ThreatActorProfile {
  actor_id: string
  actor_name: string
  generated_at: string
  tactic_coverage: TacticCoverage[]
  total_tactics_covered: number
  total_techniques: number
  campaigns: CampaignSummary[]
  ioc_breakdown: IOCCategory[]
  risk_score: number
  linked_investigation_count: number
}
