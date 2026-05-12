import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/features/auth/store";
import { AUTH_STORAGE_KEY } from "@/features/auth/constants";

export { AUTH_STORAGE_KEY };

// ── ApiError (generic so callers get typed error payloads) ───────────────────
export class ApiError<T = unknown> extends Error {
  status: number;
  data: T;

  constructor(status: number, message: string, data?: T) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data as T;
  }
}

// ── Axios client ──────────────────────────────────────────────────────────────
const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// ── Mutable refresh state (encapsulated object, not bare module globals) ──────
const refreshState = {
  isRefreshing: false,
  isRedirectingToLogin: false,
  failedQueue: [] as Array<{
    resolve: (token: string) => void;
    reject: (error: unknown) => void;
  }>,
};

function processQueue(error: unknown, token: string | null): void {
  refreshState.failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else if (token) prom.resolve(token);
  });
  refreshState.failedQueue = [];
}

function redirectToLogin(): void {
  if (refreshState.isRedirectingToLogin || window.location.pathname.startsWith("/login")) return;
  refreshState.isRedirectingToLogin = true;
  useAuthStore.getState().logout();
  // Belt-and-suspenders: clear persisted store directly so a page reload cannot
  // rehydrate stale auth state before AuthInitializer runs.
  try { localStorage.removeItem(AUTH_STORAGE_KEY); } catch { /* ignore */ }
  window.location.href = "/login";
}

// Dedicated client for the refresh call — bypasses the main interceptors to
// prevent re-entry and avoids sending the expired Bearer token.
const _refreshClient = axios.create({ withCredentials: true });

// ── Request interceptor: attach access token ──────────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Shared token refresh — deduplicates concurrent callers ───────────────────
// Both the 401 interceptor and useAuthInit use this so only one refresh call
// is ever in-flight at a time (important with rotating refresh tokens).
export async function performTokenRefresh(): Promise<string> {
  if (refreshState.isRefreshing) {
    // Another refresh is already in-flight — wait for it to finish.
    return new Promise<string>((resolve, reject) => {
      refreshState.failedQueue.push({ resolve, reject });
    });
  }

  refreshState.isRefreshing = true;
  try {
    const { data } = await _refreshClient.post<{ access_token: string }>(
      "/api/v1/auth/refresh",
      null,
    );
    const newToken = data.access_token;
    useAuthStore.getState().setAccessToken(newToken);
    processQueue(null, newToken);
    return newToken;
  } catch (err) {
    processQueue(err, null);
    throw err;
  } finally {
    refreshState.isRefreshing = false;
  }
}

// ── Response interceptor: handle 401 with token refresh ──────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const newToken = await performTokenRefresh();
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        redirectToLogin();
        return Promise.reject(refreshError);
      }
    }

    // Retried request also got 401 — session fully expired.
    if (error.response?.status === 401) {
      redirectToLogin();
      return Promise.reject(error);
    }

    const status = error.response?.status ?? 500;
    const message =
      (error.response?.data as { detail?: string })?.detail ??
      error.message ??
      "An unexpected error occurred";
    return Promise.reject(new ApiError(status, message, error.response?.data));
  },
);

export { apiClient, _refreshClient };
export default apiClient;
