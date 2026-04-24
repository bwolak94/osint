export interface DarkWebMention {
  id: string;
  source: "tor_forum" | "paste_site" | "marketplace" | "telegram_channel";
  title: string;
  snippet: string;
  query: string;
  risk_level: "critical" | "high" | "medium" | "low";
  first_seen: string;
  last_seen: string;
  url_hash: string;
  tags: string[];
}

export interface DarkWebScanResult {
  query: string;
  total_mentions: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  mentions: DarkWebMention[];
  last_scanned: string;
}
