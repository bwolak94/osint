export interface PhishingTemplate {
  id: string;
  name: string;
  category: string;
  subject: string;
  preview: string;
  success_rate_avg: number;
}

export interface PhishingCampaign {
  id: string;
  name: string;
  status: "draft" | "running" | "paused" | "completed";
  template_id: string;
  target_count: number;
  sent_count: number;
  opened_count: number;
  clicked_count: number;
  submitted_count: number;
  start_date: string | null;
  end_date: string | null;
  authorized_by: string;
  engagement_id: string;
  created_at: string;
}
