import axios, { type AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
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

// ── In-flight GET deduplication ───────────────────────────────────────────────
// Concurrent identical GETs (same URL + params) share one network request.
// Implemented via adapter wrapping so cleanup on error is guaranteed.
const _inflight = new Map<string, Promise<AxiosResponse>>();

function _dedupKey(config: InternalAxiosRequestConfig): string | null {
  if (config.method?.toUpperCase() !== "GET") return null;
  return `${config.baseURL ?? ""}${config.url ?? ""}?${JSON.stringify(config.params ?? {})}`;
}

// ── Axios client ──────────────────────────────────────────────────────────────
const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// Wrap the default adapter for transparent GET deduplication.
// Using the adapter layer (rather than interceptors) guarantees that the
// _inflight entry is always removed via .finally(), even on network errors.
const _baseAdapter = apiClient.defaults.adapter as (
  config: InternalAxiosRequestConfig,
) => Promise<AxiosResponse>;

apiClient.defaults.adapter = (config: InternalAxiosRequestConfig) => {
  const key = _dedupKey(config);
  if (!key) return _baseAdapter(config);

  const existing = _inflight.get(key);
  if (existing) return existing;

  const pending = _baseAdapter(config).finally(() => _inflight.delete(key));
  _inflight.set(key, pending);
  return pending;
};

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

// ── Response interceptor: handle 401 with token refresh ──────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (refreshState.isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshState.failedQueue.push({
            resolve: (token: string) => {
              originalRequest._retry = true;
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(apiClient(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      refreshState.isRefreshing = true;

      try {
        const { data } = await _refreshClient.post("/api/v1/auth/refresh", null);
        const newToken = data.access_token as string;
        useAuthStore.getState().setAccessToken(newToken);
        processQueue(null, newToken);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        redirectToLogin();
        return Promise.reject(refreshError);
      } finally {
        refreshState.isRefreshing = false;
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
