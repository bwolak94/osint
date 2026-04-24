export interface SlaItem {
  id: string;
  title: string;
  type: string;
  severity: string;
  engagement_id: string;
  due_date: string;
  status: "on_track" | "at_risk" | "breached" | "completed";
  days_remaining: number;
  assignee: string | null;
  escalated: boolean;
  escalation_level: number;
}

export interface SlaMetrics {
  total_items: number;
  on_track: number;
  at_risk: number;
  breached: number;
  completed: number;
  breach_rate: number;
  avg_days_remaining: number;
  items: SlaItem[];
}
