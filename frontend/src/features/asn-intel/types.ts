export interface AsnPrefix {
  prefix: string;
  name: string | null;
  description: string | null;
  country: string | null;
}

export interface AsnPeer {
  asn: number;
  name: string | null;
  description: string | null;
  country: string | null;
}

export interface AsnIntelResult {
  id: string | null;
  created_at: string | null;
  query: string;
  found: boolean;
  asn: number | null;
  name: string | null;
  description: string | null;
  country: string | null;
  website: string | null;
  email_contacts: string[];
  abuse_contacts: string[];
  rir: string | null;
  prefixes_v4: AsnPrefix[];
  prefixes_v6: AsnPrefix[];
  peers: AsnPeer[];
  upstreams: AsnPeer[];
  downstreams: AsnPeer[];
}

export interface AsnIntelListResponse {
  items: AsnIntelResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
