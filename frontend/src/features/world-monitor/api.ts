/**
 * WorldMonitor API client.
 *
 * The WorldMonitor backend exposes endpoints at /worldmonitor/api/* (not /api/v1).
 * We therefore use a dedicated axios instance so the shared client's baseURL
 * (/api/v1) does not accidentally prepend itself to our requests.
 * Auth token injection mirrors the shared client's request interceptor.
 */
import axios from 'axios'
import { useAuthStore } from '@/features/auth/store'
import type {
  BootstrapResponse,
  CategoryInfo,
  ClusterResponse,
  HealthResponse,
  NewsCategory,
  NewsResponse,
} from './types'

const wmClient = axios.create({
  baseURL: '/worldmonitor/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

wmClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── API functions ──────────────────────────────────────────────────────────

export async function fetchBootstrap(): Promise<BootstrapResponse> {
  const { data } = await wmClient.get<BootstrapResponse>('/bootstrap')
  return data
}

export async function fetchNews(params: {
  category?: NewsCategory | null
  page?: number
  page_size?: number
}): Promise<NewsResponse> {
  const { data } = await wmClient.get<NewsResponse>('/news', {
    params: {
      ...(params.category ? { category: params.category } : {}),
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  })
  return data
}

export async function fetchCategories(): Promise<CategoryInfo[]> {
  const { data } = await wmClient.get<CategoryInfo[]>('/news/categories')
  return data
}

export async function fetchClusters(): Promise<ClusterResponse> {
  const { data } = await wmClient.get<ClusterResponse>('/news/clusters')
  return data
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await wmClient.get<HealthResponse>('/health')
  return data
}
