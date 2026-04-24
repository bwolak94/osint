export interface DebriefSection {
  title: string;
  content: string;
  severity: string | null;
}

export interface AiDebrief {
  engagement_id: string;
  executive_summary: string;
  attack_narrative: string;
  key_findings: DebriefSection[];
  defensive_gaps: string[];
  recommended_priorities: string[];
  positive_findings: string[];
  metrics: Record<string, number | string>;
  generated_at: string;
}
