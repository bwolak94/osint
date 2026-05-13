export interface VehicleRecall {
  recall_id: string | null;
  component: string | null;
  summary: string | null;
  consequence: string | null;
  remedy: string | null;
  report_date: string | null;
}

export interface VehicleComplaint {
  odt_number: string | null;
  component: string | null;
  summary: string | null;
  crash: boolean;
  fire: boolean;
  date_complaint_filed: string | null;
}

export interface VehicleInfo {
  vin: string | null;
  make: string | null;
  model: string | null;
  model_year: string | null;
  vehicle_type: string | null;
  body_class: string | null;
  drive_type: string | null;
  fuel_type: string | null;
  engine_cylinders: string | null;
  engine_displacement: string | null;
  transmission: string | null;
  plant_country: string | null;
  manufacturer: string | null;
  series: string | null;
  trim: string | null;
  doors: string | null;
  error_code: string | null;
  recalls: VehicleRecall[];
  complaints_count: number;
  recent_complaints: VehicleComplaint[];
  source: string;
}

export interface VehicleOsintScan {
  id: string;
  query: string;
  query_type: string;
  total_results: number;
  results: VehicleInfo[];
  created_at: string;
}

export interface VehicleOsintListResponse {
  items: VehicleOsintScan[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
