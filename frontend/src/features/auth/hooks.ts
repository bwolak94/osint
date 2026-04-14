import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "./store";
import type { AuthResponse, LoginRequest, RegisterRequest } from "./types";

export function useLogin() {
  const login = useAuthStore((s) => s.login);

  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const response = await apiClient.post<AuthResponse>(
        "/api/v1/auth/login",
        data,
      );
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token, data.user);
    },
  });
}

export function useRegister() {
  const login = useAuthStore((s) => s.login);

  return useMutation({
    mutationFn: async (data: RegisterRequest) => {
      const response = await apiClient.post<AuthResponse>(
        "/api/v1/auth/register",
        data,
      );
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token, data.user);
    },
  });
}
