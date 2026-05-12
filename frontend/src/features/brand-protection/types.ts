export interface BrandThreat {
  id: string;
  type: "typosquat" | "phishing_site" | "fake_social" | "counterfeit_app" | "impersonation";
  target: string;
  threat_value: string;
  risk_level: string;
  first_detected: string;
  status: "active" | "taken_down" | "monitoring";
  registrar: string | null;
  hosting_ip: string | null;
  description: string;
}

export interface BrandProtectionResult {
  brand: string;
  total_threats: number;
  critical_threats: number;
  active_threats: number;
  taken_down: number;
  threats: BrandThreat[];
  monitored_domains: string[];
  last_scan: string;
}
