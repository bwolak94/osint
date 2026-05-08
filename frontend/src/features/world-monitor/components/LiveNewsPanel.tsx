import { useState } from 'react'
import { ExternalLink, RefreshCw, Rss } from 'lucide-react'
import { useNews } from '../hooks'
import type { NewsCategory } from '../types'
import { formatDistanceToNowStrict } from 'date-fns'

const CATEGORY_TABS: { label: string; value: NewsCategory | null }[] = [
  { label: 'ALL',       value: null },
  { label: 'GEO',       value: 'geopolitics' },
  { label: 'MILITARY',  value: 'military' },
  { label: 'CYBER',     value: 'cyber' },
  { label: 'ECONOMY',   value: 'economy' },
  { label: 'DISASTER',  value: 'disaster' },
  { label: 'HEALTH',    value: 'health' },
  { label: 'ENERGY',    value: 'energy' },
  { label: 'TECH',      value: 'tech' },
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
}

function timeAgo(iso: string) {
  try {
    return formatDistanceToNowStrict(new Date(iso), { addSuffix: true })
  } catch {
    return ''
  }
}

export function LiveNewsPanel() {
  const [activeCategory, setActiveCategory] = useState<NewsCategory | null>(null)
  const { data, isLoading, refetch, isFetching } = useNews(activeCategory, 1, 50)

  const items = data?.items ?? []

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex shrink-0 items-center justify-between border-b px-3 py-2"
        style={{ borderColor: 'rgba(55,65,81,0.6)' }}
      >
        <div className="flex items-center gap-2">
          <Rss className="h-3.5 w-3.5" style={{ color: '#10b981' }} />
          <span className="text-xs font-semibold tracking-wider" style={{ color: '#e5e7eb' }}>
            LIVE NEWS
          </span>
          {!isLoading && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
              style={{ background: '#10b98120', color: '#10b981' }}
            >
              {items.length}
            </span>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="rounded p-1 transition-colors hover:bg-white/5"
          title="Refresh"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? 'animate-spin' : ''}`} style={{ color: '#6b7280' }} />
        </button>
      </div>

      {/* Category tabs */}
      <div
        className="flex shrink-0 gap-1 overflow-x-auto px-2 py-1.5"
        style={{ borderBottom: '1px solid rgba(55,65,81,0.4)', scrollbarWidth: 'none' }}
      >
        {CATEGORY_TABS.map(({ label, value }) => {
          const active = activeCategory === value
          return (
            <button
              key={label}
              onClick={() => setActiveCategory(value)}
              className="shrink-0 rounded px-2 py-0.5 text-[9px] font-bold tracking-widest transition-colors"
              style={{
                background: active ? '#1d4ed820' : 'transparent',
                color: active ? '#60a5fa' : '#6b7280',
                border: `1px solid ${active ? '#3b82f640' : 'transparent'}`,
              }}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/* News list */}
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
            <Rss className="h-5 w-5" style={{ color: '#374151' }} />
            <span className="text-xs" style={{ color: '#6b7280' }}>No articles</span>
          </div>
        ) : (
          <div className="divide-y" style={{ divideColor: 'rgba(55,65,81,0.3)' }}>
            {items.map((item) => {
              const catColor = CATEGORY_COLORS[item.category] ?? '#6b7280'
              return (
                <a
                  key={item.id}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex gap-2 px-3 py-2.5 transition-colors hover:bg-white/5"
                >
                  <div
                    className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: catColor, boxShadow: `0 0 4px ${catColor}` }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-snug line-clamp-2 transition-colors group-hover:text-white" style={{ color: '#d1d5db' }}>
                      {item.title}
                    </p>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className="text-[9px] font-medium uppercase" style={{ color: catColor }}>
                        {item.category}
                      </span>
                      <span style={{ color: '#374151' }}>·</span>
                      <span className="text-[9px]" style={{ color: '#6b7280' }}>
                        {item.source_name}
                      </span>
                      <span style={{ color: '#374151' }}>·</span>
                      <span className="text-[9px]" style={{ color: '#4b5563' }}>
                        {timeAgo(item.published_at)}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className="h-3 w-3 shrink-0 self-start mt-1 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: '#6b7280' }} />
                </a>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
