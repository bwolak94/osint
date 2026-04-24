export interface PhoneCarrierInfo {
  name: string;
  type: string;
  country: string;
  country_code: string;
}

export interface PhoneIntelResult {
  phone_number: string;
  formatted: string;
  country: string;
  country_code: string;
  carrier: PhoneCarrierInfo;
  line_type: string;
  is_valid: boolean;
  is_disposable: boolean;
  is_voip: boolean;
  timezone: string;
  location: string | null;
  spam_score: number;
  spam_reports: number;
  breach_count: number;
  social_profiles_found: string[];
  associated_emails: string[];
  associated_names: string[];
  risk_level: string;
}
