export interface ThreatIndicator {
  id: string;
  type: string;
  value: string;
  confidence: number;
  severity: string;
  tags: string[];
  first_seen: string;
  last_seen: string;
  ttl_days: number;
  tlp: string;
}

export interface ThreatFeed {
  id: string;
  name: string;
  description: string;
  format: string;
  status: string;
  indicator_count: number;
  subscribers: number;
  last_updated: string;
  indicators: ThreatIndicator[];
}

export interface CreateFeedInput {
  name: string;
  description: string;
  format?: string;
  tlp?: string;
}
