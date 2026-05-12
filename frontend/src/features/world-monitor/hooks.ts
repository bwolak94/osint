import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBootstrap, fetchCategories, fetchHealth, fetchMapEvents, fetchNews, fetchPosts } from './api'
import type { NewsCategory, NewsItem } from './types'
import { useAuthStore } from '@/features/auth/store'

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

/**
 * SSE hook — opens a persistent connection to /worldmonitor/api/stream and
 * calls `onNewItem` for every `event: news` message received.
 * Automatically reconnects after 30 s on error / disconnect.
 */
export function useNewsStream(onNewItem: (item: NewsItem) => void): void {
  const cbRef = useRef(onNewItem)
  cbRef.current = onNewItem

  useEffect(() => {
    let active = true
    const ac = new AbortController()

    async function connect(): Promise<void> {
      const token = useAuthStore.getState().accessToken
      try {
        const res = await fetch('/worldmonitor/api/stream', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: ac.signal,
        })
        if (!res.ok || !res.body) return

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        let evtName = ''
        let evtData = ''

        while (active) {
          const { done, value } = await reader.read()
          if (done) break

          buf += decoder.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              evtName = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              evtData = line.slice(6)
            } else if (line === '') {
              if (evtName === 'news' && evtData) {
                try {
                  cbRef.current(JSON.parse(evtData) as NewsItem)
                } catch { /* ignore malformed */ }
              }
              evtName = ''
              evtData = ''
            }
          }
        }
      } catch {
        if (!active) return
        await new Promise<void>((r) => setTimeout(r, 30_000))
        if (active) void connect()
      }
    }

    void connect()
    return () => {
      active = false
      ac.abort()
    }
  }, [])
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
