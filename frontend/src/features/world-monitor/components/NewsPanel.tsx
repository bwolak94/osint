import { useState, useCallback } from 'react'
import { ExternalLink, RefreshCw, Rss } from 'lucide-react'
import { useNews } from '../hooks'
import { CategoryFilter } from './CategoryFilter'
import type { NewsCategory, NewsItem } from '../types'

const CATEGORY_COLORS: Record<string, string> = {
  geopolitics: 'var(--brand-500)',
  military: '#ef4444',
  cyber: '#f59e0b',
  economy: '#10b981',
  climate: '#06b6d4',
  disaster: '#f97316',
  health: '#ec4899',
  energy: '#8b5cf6',
  tech: '#6366f1',
}

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

interface NewsCardProps {
  item: NewsItem
}

function NewsCard({ item }: NewsCardProps) {
  const catColor = CATEGORY_COLORS[item.category] ?? 'var(--text-tertiary)'

  return (
    <article
      className="group flex flex-col gap-1 rounded-md border p-3 transition-colors hover:border-brand-500/30"
      style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 text-sm font-medium leading-snug transition-colors hover:underline"
          style={{ color: 'var(--text-primary)' }}
        >
          {item.title}
        </a>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open article"
          className="mt-0.5 flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
          style={{ color: 'var(--text-tertiary)' }}
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>

      {item.description && (
        <p className="line-clamp-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {item.description}
        </p>
      )}

      <div className="mt-1 flex items-center gap-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        <span
          className="rounded-full px-1.5 py-0.5 font-medium"
          style={{ background: `${catColor}18`, color: catColor }}
        >
          {item.category}
        </span>
        <span className="uppercase tracking-wide">{item.country_iso}</span>
        <span className="ml-auto">{item.source_name}</span>
        <span aria-label={`Published ${item.published_at}`}>{timeAgo(item.published_at)}</span>
      </div>
    </article>
  )
}

interface NewsPanelProps {
  initialCategories: string[]
}

export function NewsPanel({ initialCategories }: NewsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<NewsCategory | null>(null)
  const [page, setPage] = useState(1)

  const { data, isLoading, isFetching, refetch } = useNews(activeCategory, page)

  const handleCategoryChange = useCallback((cat: NewsCategory | null) => {
    setActiveCategory(cat)
    setPage(1)
  }, [])

  const items: NewsItem[] = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Rss className="h-4 w-4" style={{ color: 'var(--brand-500)' }} aria-hidden="true" />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Live News Feed
          </span>
          {total > 0 && (
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {total} items
            </span>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          aria-label="Refresh news"
          className="rounded p-1 transition-colors hover:bg-white/5 disabled:opacity-40"
          style={{ color: 'var(--text-tertiary)' }}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Category tabs */}
      <CategoryFilter
        categories={initialCategories}
        active={activeCategory}
        onChange={handleCategoryChange}
      />

      {/* News list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-md"
                style={{ background: 'var(--bg-elevated)' }}
                aria-hidden="true"
              />
            ))}
          </div>
        )}

        {!isLoading && items.length === 0 && (
          <div
            className="flex flex-col items-center justify-center rounded-md border py-12 text-center"
            style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}
          >
            <Rss className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
              {activeCategory
                ? `No articles yet for "${activeCategory}"`
                : 'Feed is warming up — check back in a minute'}
            </p>
          </div>
        )}

        {!isLoading && items.length > 0 && (
          <div className="flex flex-col gap-2">
            {items.map((item) => (
              <NewsCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)' }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || isFetching}
            className="rounded px-3 py-1 text-xs transition-colors hover:bg-white/5 disabled:opacity-30"
            style={{ color: 'var(--text-secondary)' }}
          >
            Previous
          </button>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Page {page}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={items.length < 50 || isFetching}
            className="rounded px-3 py-1 text-xs transition-colors hover:bg-white/5 disabled:opacity-30"
            style={{ color: 'var(--text-secondary)' }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
