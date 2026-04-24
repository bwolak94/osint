export interface DnsRecord {
  id: string;
  timestamp: string;
  record_type: string;
  name: string;
  value: string;
  ttl: number;
  source: string;
  first_seen: string;
  last_seen: string;
  count: number;
}

export interface PassiveDnsResult {
  query: string;
  total_records: number;
  unique_ips: number;
  date_range_start: string;
  date_range_end: string;
  records: DnsRecord[];
  ip_history: Array<{ ip: string; first_seen: string; asn: string; org: string }>;
}
