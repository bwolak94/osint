export interface ScannerStep {
  id: string;
  type: string;
  config: Record<string, unknown>;
  output_key: string;
}

export interface CustomScanner {
  id: string;
  name: string;
  description: string;
  input_type: string;
  steps: ScannerStep[];
  enabled: boolean;
  run_count: number;
  last_run: string | null;
  created_at: string;
}

export interface CreateScannerInput {
  name: string;
  description: string;
  input_type?: string;
}

export interface ScanResult {
  scanner_id: string;
  input: string;
  results: Record<string, string>;
  status: string;
}
