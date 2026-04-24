export interface Vulnerability {
  id: string;
  cve_id: string | null;
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  cvss_score: number;
  category: string;
  status: "open" | "in_progress" | "remediated" | "accepted_risk";
  affected_assets: string[];
  description: string;
  remediation: string;
  discovered_at: string;
  due_date: string | null;
  assignee: string | null;
  tags: string[];
}
