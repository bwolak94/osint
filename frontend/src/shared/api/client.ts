import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// Request interceptor: attach access token
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Dynamic import to avoid circular deps
  const token = getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 with refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else if (token) prom.resolve(token);
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
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
      isRefreshing = true;

      try {
        const { data } = await axios.post("/api/v1/auth/refresh", null, {
          withCredentials: true,
        });
        const newToken = data.access_token;
        setAccessToken(newToken);
        processQueue(null, newToken);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearAuth();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Any unhandled 401 — clear auth and redirect to login
    if (error.response?.status === 401) {
      clearAuth();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
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

// Token accessors — read/write from in-memory zustand store (not localStorage)
function getAccessToken(): string | null {
  try {
    const { useAuthStore } = require("@/features/auth/store");
    return useAuthStore.getState().accessToken;
  } catch {
    return null;
  }
}

function setAccessToken(token: string): void {
  try {
    const { useAuthStore } = require("@/features/auth/store");
    useAuthStore.getState().setAccessToken(token);
  } catch {}
}

function clearAuth(): void {
  try {
    const { useAuthStore } = require("@/features/auth/store");
    useAuthStore.getState().logout();
  } catch {}
}

export { apiClient };
export default apiClient;
