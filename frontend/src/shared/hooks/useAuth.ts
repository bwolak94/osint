import { useAuthStore } from "@/features/auth/store";

/**
 * Convenience hook wrapping the auth store.
 * Provides current user, token, and auth actions.
 */
export function useAuth() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const login = useAuthStore((s) => s.login);
  const logout = useAuthStore((s) => s.logout);

  const isAuthenticated = !!token;

  return { token, user, isAuthenticated, login, logout };
}
