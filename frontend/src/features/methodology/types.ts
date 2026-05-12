export interface MethodologyStep {
  id: string;
  phase: string;
  name: string;
  description: string;
  required: boolean;
  checklist_items: string[];
  references: string[];
}

export interface Assessment {
  id: string;
  name: string;
  methodology: string;
  status: string;
  completed_steps: string[];
  total_steps: number;
  completion_percentage: number;
  created_at: string;
  engagement_id: string;
}
