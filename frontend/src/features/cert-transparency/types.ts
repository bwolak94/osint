export interface CertRecord {
  id: string;
  common_name: string;
  san_domains: string[];
  issuer: string;
  not_before: string;
  not_after: string;
  serial_number: string;
  fingerprint_sha256: string;
  ct_logs: string[];
  is_wildcard: boolean;
  is_expired: boolean;
  days_until_expiry: number | null;
}

export interface CertTransparencyResult {
  query: string;
  total_certs: number;
  wildcard_count: number;
  expiring_soon: number;
  expired_count: number;
  certs: CertRecord[];
}
