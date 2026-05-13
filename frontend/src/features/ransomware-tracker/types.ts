export interface RansomwareVictim {
  victim: string;
  group: string | null;
  country: string | null;
  activity: string | null;
  discovered: string | null;
  description: string | null;
  url: string | null;
  tags: string[];
}

export interface RansomwareGroup {
  name: string;
  description: string | null;
  locations: string[];
  profile_url: string | null;
}

export interface RansomwareTrackerResult {
  query: string;
  total_victims: number;
  victims: RansomwareVictim[];
  group_info: RansomwareGroup | null;
}
