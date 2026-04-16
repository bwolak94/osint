export interface UserSettings {
  theme: "dark" | "light" | "system";
  language: "pl" | "en";
  date_format: string;
  timezone: string;
  email_on_scan_complete: boolean;
  email_on_new_findings: boolean;
  email_weekly_digest: boolean;
  default_scan_depth: number;
  default_enabled_scanners: string[];
  default_tags: string[];
  anonymize_exports: boolean;
  data_retention_days: number;
  has_api_key: boolean;
  api_key_prefix: string | null;
  api_key_created_at: string | null;
  gdpr_consent_given_at: string | null;
  marketing_consent: boolean;
}

export interface Session {
  id: string;
  device: string;
  browser: string;
  location: string;
  last_active: string;
  is_current: boolean;
}
