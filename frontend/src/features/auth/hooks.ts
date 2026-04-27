import { useEffect, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient, _refreshClient } from "@/shared/api/client";
import { useAuthStore } from "./store";

// 25 minutes — refresh proactively 5 min before the 30-min access token expires
const PROACTIVE_REFRESH_MS = 25 * 60 * 1000;

/**
 * Call once at the app root. Silently refreshes the access token on page load
 * (when isAuthenticated but accessToken is null after rehydration) and sets up
 * a repeating 25-minute timer to keep the token fresh without ever hitting 401.
 */
export function useAuthInit(): void {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const logout = useAuthStore((s) => s.logout);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const silentRefresh = async (): Promise<void> => {
    try {
      const { data } = await _refreshClient.post<{ access_token: string }>(
        "/api/v1/auth/refresh",
        null,
      );
      setAccessToken(data.access_token);
    } catch {
      // Refresh token expired or missing — force logout
      logout();
    }
  };

  useEffect(() => {
    if (!isAuthenticated) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    // On page load accessToken is null (not persisted) — refresh immediately
    if (!accessToken) {
      silentRefresh();
    }

    // Proactive refresh every 25 min regardless of activity
    timerRef.current = setInterval(silentRefresh, PROACTIVE_REFRESH_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);
}

interface LoginRequest { email: string; password: string; }
interface RegisterRequest { email: string; password: string; fullName?: string; companyName?: string; }
interface AuthResponse { access_token: string; user: { id: string; email: string; role: string; subscription_tier: string; is_active: boolean; is_email_verified: boolean; tos_accepted_at?: string | null; }; }

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth);
  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const res = await apiClient.post<AuthResponse>("/auth/login", data);
      return res.data;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterRequest) => {
      const res = await apiClient.post<AuthResponse>("/auth/register", data);
      return res.data;
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  return useMutation({
    mutationFn: async () => {
      await apiClient.post("/auth/logout");
    },
    onSettled: () => { logout(); },
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) => {
      await apiClient.post("/auth/forgot-password", { email });
    },
  });
}
