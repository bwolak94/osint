export interface TimeEntry {
  id: string;
  engagement_id: string;
  category: string;
  description: string;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  billable: boolean;
  hourly_rate: number;
  amount: number;
  created_at: string;
}
