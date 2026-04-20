import { useAuthStore } from "@/features/auth/store";

export function useAuth() {
  const { user, accessToken, isAuthenticated, setAuth, setAccessToken, logout } = useAuthStore();

  return {
    user,
    accessToken,
    isAuthenticated,
    isAdmin: user?.role === "admin",
    isPro: user?.subscription_tier === "pro" || user?.subscription_tier === "enterprise",
    isEnterprise: user?.subscription_tier === "enterprise",
    setAuth,
    setAccessToken,
    logout,
  };
}
