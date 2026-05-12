export interface FootprintCategory {
  name: string;
  score: number;
  findings: string[];
  risk: "low" | "medium" | "high" | "critical";
}

export interface FootprintScore {
  target: string;
  overall_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  categories: FootprintCategory[];
  exposed_assets: string[];
  recommendations: string[];
  data_broker_count: number;
  social_profiles: Array<{ platform: string; url_found: boolean; privacy: string }>;
}
