import { useQuery } from '@tanstack/react-query'
import { fetchBootstrap, fetchCategories, fetchHealth, fetchNews } from './api'
import type { NewsCategory } from './types'

const KEYS = {
  bootstrap: ['world-monitor', 'bootstrap'] as const,
  news: (category: NewsCategory | null, page: number) =>
    ['world-monitor', 'news', category, page] as const,
  categories: ['world-monitor', 'categories'] as const,
  health: ['world-monitor', 'health'] as const,
}

/** Initial data load for the dashboard — fast, cached 5 min. */
export function useWorldMonitorBootstrap() {
  return useQuery({
    queryKey: KEYS.bootstrap,
    queryFn: fetchBootstrap,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })
}

/**
 * Paginated news feed, auto-refreshes every 60 s for a live feel.
 * Falls back to bootstrap data while loading subsequent pages.
 */
export function useNews(
  category: NewsCategory | null = null,
  page = 1,
  pageSize = 50,
) {
  return useQuery({
    queryKey: KEYS.news(category, page),
    queryFn: () => fetchNews({ category, page, page_size: pageSize }),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
    retry: 1,
  })
}

/** Feed categories with item counts. */
export function useCategories() {
  return useQuery({
    queryKey: KEYS.categories,
    queryFn: fetchCategories,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })
}

/** WorldMonitor health — refreshes every 30 s. */
export function useWorldMonitorHealth() {
  return useQuery({
    queryKey: KEYS.health,
    queryFn: fetchHealth,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
    retry: 1,
  })
}
