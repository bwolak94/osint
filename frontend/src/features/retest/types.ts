export interface RetestItem {
  id: string;
  finding_id: string;
  finding_title: string;
  severity: "critical" | "high" | "medium" | "low";
  original_cvss: number;
  status: "pending" | "in_progress" | "passed" | "failed" | "skipped";
  result: string | null;
  tested_at: string | null;
  notes: string;
  automated: boolean;
}

export interface RetestSession {
  id: string;
  name: string;
  engagement_id: string;
  items: RetestItem[];
  total_items: number;
  passed: number;
  failed: number;
  pending: number;
  completion_percentage: number;
  created_at: string;
  status: string;
}
