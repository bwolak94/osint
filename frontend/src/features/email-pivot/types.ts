export interface LinkedAccount {
  platform: string;
  profile_url: string | null;
  display_name: string | null;
  avatar_url: string | null;
  exists: boolean;
}

export interface EmailPivotResult {
  email: string;
  domain: string | null;
  gravatar_exists: boolean;
  gravatar_display_name: string | null;
  gravatar_avatar_url: string | null;
  gravatar_profile_url: string | null;
  github_username: string | null;
  github_profile_url: string | null;
  hibp_breaches: string[];
  hibp_checked: boolean;
  disposable: boolean;
  linked_accounts: LinkedAccount[];
}
