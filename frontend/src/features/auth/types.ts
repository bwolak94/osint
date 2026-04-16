export interface User {
  id: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
  subscription_tier: "free" | "pro" | "enterprise";
  is_active: boolean;
  is_email_verified: boolean;
}

export interface LoginRequest { email: string; password: string; }
export interface RegisterRequest { email: string; password: string; fullName?: string; companyName?: string; termsAccepted: boolean; privacyAccepted: boolean; marketingConsent: boolean; }
export interface AuthResponse { access_token: string; token_type: string; user: User; }
