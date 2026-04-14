export interface UserSettings {
  id: string;
  email: string;
  username: string;
  notifications_enabled: boolean;
  theme: "light" | "dark";
}

export interface UpdateSettingsRequest {
  username?: string;
  notifications_enabled?: boolean;
  theme?: "light" | "dark";
}
