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
