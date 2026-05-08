import { useQuery } from '@tanstack/react-query'
import { fetchBootstrap, fetchCategories, fetchHealth, fetchMapEvents, fetchNews, fetchPosts } from './api'
import type { NewsCategory } from './types'

const KEYS = {
  bootstrap: ['world-monitor', 'bootstrap'] as const,
  // pageSize is included in the key so callers with different page sizes don't
  // share cache entries and accidentally serve wrong data
  news: (category: NewsCategory | null, page: number, pageSize: number) =>
    ['world-monitor', 'news', category, page, pageSize] as const,
  categories: ['world-monitor', 'categories'] as const,
  health: ['world-monitor', 'health'] as const,
  mapEvents: (layer: string | null) => ['world-monitor', 'map-events', layer] as const,
  posts: (platform: string | null) => ['world-monitor', 'posts', platform] as const,
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
    queryKey: KEYS.news(category, page, pageSize),
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

/**
 * Live geospatial map events (USGS, NASA EONET, GDACS, Feodo Tracker).
 * Auto-refreshes every 10 min to match backend aggregation interval.
 */
/** Social posts from X and Truth Social, refreshes every 5 min. */
export function usePosts(platform: 'x' | 'truthsocial' | null = null) {
  return useQuery({
    queryKey: KEYS.posts(platform),
    queryFn: () => fetchPosts({ platform }),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: 1,
  })
}

export function useMapEvents(layer: string | null = null) {
  return useQuery({
    queryKey: KEYS.mapEvents(layer),
    queryFn: () => fetchMapEvents({ layer }),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    retry: 1,
  })
}
