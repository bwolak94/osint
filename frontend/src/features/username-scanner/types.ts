export interface PlatformResult {
  platform: string;
  url: string;
  found: boolean;
  status_code: number | null;
  error: string | null;
}

export interface UsernameScanResult {
  username: string;
  total_checked: number;
  found: PlatformResult[];
  not_found: PlatformResult[];
  errors: PlatformResult[];
}
