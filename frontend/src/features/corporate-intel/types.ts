export interface Executive {
  name: string;
  title: string;
  linkedin_found: boolean;
  email_pattern: string | null;
  previous_companies: string[];
}

export interface Subsidiary {
  name: string;
  country: string;
  registration_number: string | null;
  active: boolean;
}

export interface CorporateProfile {
  company_name: string;
  registration_number: string | null;
  country: string;
  industry: string;
  founded_year: number | null;
  employee_count_range: string;
  revenue_range: string | null;
  website: string;
  technologies: string[];
  executives: Executive[];
  subsidiaries: Subsidiary[];
  domains: string[];
  ip_ranges: string[];
  open_jobs: number;
  news_count: number;
  risk_indicators: string[];
}
