import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "./store";

interface LoginRequest { email: string; password: string; }
interface RegisterRequest { email: string; password: string; fullName?: string; companyName?: string; }
interface AuthResponse { access_token: string; user: { id: string; email: string; role: string; subscription_tier: string; is_active: boolean; is_email_verified: boolean; }; }

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
