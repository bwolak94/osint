import { create } from "zustand";
import { persist } from "zustand/middleware";
import { AUTH_STORAGE_KEY } from "./constants";

interface User {
  id: string;
  email: string;
  role: string;
  subscription_tier: string;
  is_active: boolean;
  is_email_verified: boolean;
  tos_accepted_at?: string | null;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, token: string) => void;
  setAccessToken: (token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      setAuth: (user, token) =>
        set({ user, accessToken: token, isAuthenticated: true }),
      setAccessToken: (token) => set({ accessToken: token }),
      logout: () =>
        set({ user: null, accessToken: null, isAuthenticated: false }),
    }),
    {
      name: AUTH_STORAGE_KEY,
      // accessToken is intentionally NOT persisted — it lives in memory only.
      // On page reload the token is gone; AuthInitializer does a silent refresh
      // using the httpOnly refresh cookie to get a fresh one without a 401.
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
