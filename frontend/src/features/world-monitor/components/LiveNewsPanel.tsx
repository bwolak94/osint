import { useCallback, useMemo, useState } from 'react'
import { Clock, ExternalLink, RefreshCw, Rss, Twitter, Zap } from 'lucide-react'
import { useNews, useNewsStream, usePosts } from '../hooks'
import { NewsDetailModal } from './NewsDetailModal'
import type { NewsCategory, NewsItem, PostItem } from '../types'
import { formatDistanceToNowStrict, subMinutes } from 'date-fns'

type AnyItem = NewsItem | PostItem
type Mode = 'news' | 'social'

const NEWS_TABS: { label: string; value: NewsCategory | null }[] = [
  { label: 'ALL',      value: null },
  { label: 'GEO',      value: 'geopolitics' },
  { label: 'MIL',      value: 'military' },
  { label: 'CYBER',    value: 'cyber' },
  { label: 'ECON',     value: 'economy' },
  { label: 'DISASTER', value: 'disaster' },
  { label: 'CLIMATE',  value: 'climate' },
  { label: 'HEALTH',   value: 'health' },
  { label: 'ENERGY',   value: 'energy' },
  { label: 'TECH',     value: 'tech' },
]

const TIME_FILTERS: { label: string; minutes: number | null }[] = [
  { label: 'ALL',  minutes: null },
  { label: '15m',  minutes: 15 },
  { label: '1h',   minutes: 60 },
  { label: '6h',   minutes: 360 },
  { label: '24h',  minutes: 1440 },
  { label: '7d',   minutes: 10080 },
]

const CATEGORY_COLORS: Record<string, string> = {
  geopolitics: '#ef4444',
  military:    '#3b82f6',
  cyber:       '#10b981',
  economy:     '#eab308',
  disaster:    '#f97316',
  health:      '#ec4899',
  energy:      '#6366f1',
  tech:        '#8b5cf6',
  climate:     '#06b6d4',
  social:      '#1d9bf0',
}

function timeAgo(iso: string) {
  try { return formatDistanceToNowStrict(new Date(iso), { addSuffix: true }) }
  catch { return '' }
}

function NewsRow({ item, onClick }: { item: AnyItem; onClick: () => void }) {
  const isPost = item.category === 'social'
  const post = isPost ? (item as PostItem) : null
  const catColor = CATEGORY_COLORS[item.category] ?? '#6b7280'

  return (
    <button
      onClick={onClick}
      className="group flex w-full gap-2 px-3 py-2.5 text-left transition-colors hover:bg-white/5"
      style={{ borderBottom: '1px solid rgba(55,65,81,0.2)' }}
    >
      {item.image_url ? (
        <div className="mt-0.5 h-10 w-14 shrink-0 overflow-hidden rounded">
          <img
            src={item.image_url}
            alt=""
            className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        </div>
      ) : (
        <div
          className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: catColor, boxShadow: `0 0 4px ${catColor}` }}
        />
      )}

      <div className="min-w-0 flex-1">
        <p className="text-xs leading-snug line-clamp-2 transition-colors group-hover:text-white" style={{ color: '#d1d5db' }}>
          {item.title}
        </p>
        <div className="mt-1 flex items-center gap-1.5 flex-wrap">
          <span className="text-[9px] font-medium uppercase" style={{ color: catColor }}>
            {isPost
              ? (post?.platform === 'x' ? '𝕏' : post?.platform === 'official' ? post?.display_name?.split(' ')[0] : 'TRUTH')
              : item.category}
          </span>
          <span style={{ color: '#374151' }}>·</span>
          <span className="text-[9px]" style={{ color: '#6b7280' }}>
            {isPost ? post?.display_name : (item as NewsItem).source_name}
          </span>
          <span style={{ color: '#374151' }}>·</span>
          <span className="text-[9px]" style={{ color: '#4b5563' }}>
            {timeAgo(item.published_at)}
          </span>
        </div>
      </div>
      <ExternalLink className="h-3 w-3 shrink-0 self-start mt-1 opacity-0 group-hover:opacity-60 transition-opacity" style={{ color: '#6b7280' }} />
    </button>
  )
}

export function LiveNewsPanel() {
  const [mode, setMode]               = useState<Mode>('news')
  const [activeCategory, setCategory] = useState<NewsCategory | null>(null)
  const [timeWindow, setTimeWindow]   = useState<number | null>(null)
  const [selectedItem, setSelected]   = useState<AnyItem | null>(null)
  // Items pushed via SSE that haven't yet appeared in the next poll cycle
  const [streamedItems, setStreamedItems] = useState<NewsItem[]>([])
  const [streamCount, setStreamCount]     = useState(0)

  // Category is sent to backend (uses per-category Redis key); time filter is client-side only
  const { data: newsData, isLoading: newsLoading, refetch: refetchNews, isFetching: newsFetching } = useNews(activeCategory, 1, 200)
  // Prefetch counts for each tab using the full unfiltered set
  const { data: allNewsData } = useNews(null, 1, 500)
  const { data: postsData, isLoading: postsLoading, refetch: refetchPosts, isFetching: postsFetching } = usePosts()

  // Wire up SSE stream — appends new items instantly without waiting for poll
  const handleNewItem = useCallback((item: NewsItem) => {
    setStreamedItems((prev) => {
      // Skip duplicates
      if (prev.some((p) => p.id === item.id)) return prev
      setStreamCount((c) => c + 1)
      return [item, ...prev].slice(0, 100) // keep ring buffer small
    })
  }, [])
  useNewsStream(handleNewItem)

  const isLoading = mode === 'news' ? newsLoading : postsLoading
  const isFetching = mode === 'news' ? newsFetching : postsFetching

  const items = useMemo<AnyItem[]>(() => {
    const cutoff = timeWindow !== null ? subMinutes(new Date(), timeWindow) : null

    if (mode === 'social') {
      const all = postsData?.items ?? []
      return cutoff ? all.filter(p => new Date(p.published_at) >= cutoff) : all
    }

    // Merge SSE-streamed items with polled items; deduplicate by id
    const polled: NewsItem[] = newsData?.items ?? []
    const seenIds = new Set(polled.map((i) => i.id))
    const streamed = streamedItems.filter(
      (i) =>
        !seenIds.has(i.id) &&
        (activeCategory === null || i.category === activeCategory),
    )
    let all: AnyItem[] = [...streamed, ...polled]
    if (cutoff) {
      all = all.filter(item => new Date(item.published_at) >= cutoff)
    }
    return all
  }, [mode, newsData, postsData, streamedItems, activeCategory, timeWindow])

  // Tab counts come from the balanced all-categories response
  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: allNewsData?.total ?? allNewsData?.items?.length ?? 0 }
    for (const item of allNewsData?.items ?? []) {
      counts[item.category] = (counts[item.category] ?? 0) + 1
    }
    return counts
  }, [allNewsData])

  const handleRefetch = () => mode === 'news' ? refetchNews() : refetchPosts()

  return (
    <>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div
          className="flex shrink-0 items-center justify-between border-b px-3 py-2"
          style={{ borderColor: 'rgba(55,65,81,0.6)' }}
        >
          <div className="flex items-center gap-2">
            <Rss className="h-3.5 w-3.5" style={{ color: '#10b981' }} />
            <span className="text-xs font-semibold tracking-wider" style={{ color: '#e5e7eb' }}>LIVE NEWS</span>
            {!isLoading && (
              <span className="rounded-full px-1.5 py-0.5 text-[9px] font-medium" style={{ background: '#10b98120', color: '#10b981' }}>
                {items.length}
              </span>
            )}
            {streamCount > 0 && (
              <span
                className="flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold"
                style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)' }}
                title="Items received via live stream"
              >
                <Zap className="h-2 w-2" />
                +{streamCount}
              </span>
            )}
          </div>
          <button onClick={handleRefetch} disabled={isFetching} className="rounded p-1 transition-colors hover:bg-white/5" title="Refresh">
            <RefreshCw className={`h-3 w-3 ${isFetching ? 'animate-spin' : ''}`} style={{ color: '#6b7280' }} />
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex shrink-0 gap-1 px-2 py-1.5" style={{ borderBottom: '1px solid rgba(55,65,81,0.4)' }}>
          {(['news', 'social'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="flex items-center gap-1 rounded px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest transition-colors"
              style={{
                background: mode === m ? (m === 'social' ? '#1d9bf020' : '#10b98120') : 'transparent',
                color: mode === m ? (m === 'social' ? '#1d9bf0' : '#10b981') : '#4b5563',
                border: `1px solid ${mode === m ? (m === 'social' ? '#1d9bf040' : '#10b98140') : 'transparent'}`,
              }}
            >
              {m === 'social' && <Twitter className="h-2.5 w-2.5" />}
              {m === 'news' ? 'News Feeds' : 'Social Posts'}
            </button>
          ))}
        </div>

        {/* Category tabs — news mode only */}
        {mode === 'news' && (
          <div
            className="flex shrink-0 gap-1 overflow-x-auto px-2 py-1.5"
            style={{ borderBottom: '1px solid rgba(55,65,81,0.4)', scrollbarWidth: 'none' }}
          >
            {NEWS_TABS.map(({ label, value }) => {
              const active = activeCategory === value
              const count = value === null ? (tabCounts['ALL'] ?? 0) : (tabCounts[value] ?? 0)
              return (
                <button
                  key={label}
                  onClick={() => setCategory(value)}
                  className="shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[9px] font-bold tracking-widest transition-colors"
                  style={{
                    background: active ? '#1d4ed820' : 'transparent',
                    color: active ? '#60a5fa' : '#6b7280',
                    border: `1px solid ${active ? '#3b82f640' : 'transparent'}`,
                  }}
                >
                  {label}
                  {count > 0 && (
                    <span className="text-[8px]" style={{ color: active ? '#60a5fa99' : '#4b5563' }}>
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {/* Time filter */}
        <div
          className="flex shrink-0 items-center gap-1 overflow-x-auto px-2 py-1"
          style={{ borderBottom: '1px solid rgba(55,65,81,0.3)', scrollbarWidth: 'none' }}
        >
          <Clock className="h-2.5 w-2.5 shrink-0" style={{ color: '#4b5563' }} />
          {TIME_FILTERS.map(({ label, minutes }) => {
            const active = timeWindow === minutes
            return (
              <button
                key={label}
                onClick={() => setTimeWindow(minutes)}
                className="shrink-0 rounded px-2 py-0.5 text-[9px] font-bold tracking-widest transition-colors"
                style={{
                  background: active ? '#78350f30' : 'transparent',
                  color: active ? '#f59e0b' : '#4b5563',
                  border: `1px solid ${active ? '#f59e0b40' : 'transparent'}`,
                }}
              >
                {label}
              </button>
            )
          })}
        </div>

        {/* List */}
        <div className="min-h-0 flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
          {isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="h-2.5 w-4/5 animate-pulse rounded" style={{ background: '#1f2937' }} />
                  <div className="h-2 w-1/3 animate-pulse rounded" style={{ background: '#1f2937' }} />
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2">
              {mode === 'social'
                ? <Twitter className="h-5 w-5" style={{ color: '#374151' }} />
                : <Rss className="h-5 w-5" style={{ color: '#374151' }} />
              }
              <span className="text-xs" style={{ color: '#6b7280' }}>
                {mode === 'social' ? 'No posts yet — fetching…' : 'No articles in this filter'}
              </span>
            </div>
          ) : (
            <div>
              {items.map((item) => (
                <NewsRow key={item.id} item={item} onClick={() => setSelected(item)} />
              ))}
            </div>
          )}
        </div>
      </div>

      <NewsDetailModal item={selectedItem} onClose={() => setSelected(null)} />
    </>
  )
}
