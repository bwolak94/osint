import { useEffect, useCallback } from 'react'
import { X, ExternalLink, Clock, Globe, Twitter, AlertCircle } from 'lucide-react'
import { formatDistanceToNowStrict } from 'date-fns'
import type { NewsItem, PostItem } from '../types'

type AnyItem = NewsItem | PostItem

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

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  x:            <Twitter className="h-3.5 w-3.5" />,
  truthsocial:  <AlertCircle className="h-3.5 w-3.5" />,
}

function timeAgo(iso: string) {
  try { return formatDistanceToNowStrict(new Date(iso), { addSuffix: true }) }
  catch { return '' }
}

function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim()
}

interface Props {
  item: AnyItem | null
  onClose: () => void
}

export function NewsDetailModal({ item, onClose }: Props) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    if (!item) return
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [item, handleKeyDown])

  if (!item) return null

  const catColor = CATEGORY_COLORS[item.category] ?? '#6b7280'
  const isPost = item.category === 'social'
  const post = isPost ? (item as PostItem) : null
  const description = stripHtml(item.description || '')
  const imageUrl = item.image_url

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      {/* Modal */}
      <div
        className="relative flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl"
        style={{
          background: '#0f1117',
          border: '1px solid rgba(55,65,81,0.7)',
          boxShadow: '0 25px 60px rgba(0,0,0,0.8)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header bar */}
        <div
          className="flex shrink-0 items-center justify-between px-4 py-3"
          style={{ borderBottom: '1px solid rgba(55,65,81,0.5)', background: 'rgba(17,24,39,0.8)' }}
        >
          <div className="flex items-center gap-2">
            {/* Category badge */}
            <span
              className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest"
              style={{ background: `${catColor}20`, color: catColor, border: `1px solid ${catColor}40` }}
            >
              {item.category}
            </span>
            {/* Platform badge for social posts */}
            {post && (
              <span
                className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium"
                style={{ background: 'rgba(29,155,240,0.15)', color: '#1d9bf0', border: '1px solid rgba(29,155,240,0.3)' }}
              >
                {PLATFORM_ICONS[post.platform]}
                {post.platform === 'x' ? 'X / Twitter' : 'Truth Social'}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors hover:bg-white/10"
            aria-label="Close"
          >
            <X className="h-4 w-4" style={{ color: '#9ca3af' }} />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="min-h-0 flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>

          {/* Image */}
          {imageUrl && (
            <div className="relative h-52 w-full overflow-hidden shrink-0">
              <img
                src={imageUrl}
                alt=""
                className="h-full w-full object-cover"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
              />
              <div className="absolute inset-0" style={{ background: 'linear-gradient(to bottom, transparent 50%, #0f1117)' }} />
            </div>
          )}

          {/* Body */}
          <div className="px-5 py-4 space-y-4">
            {/* Title */}
            <h2 className="text-base font-semibold leading-snug" style={{ color: '#f9fafb', fontFamily: "'JetBrains Mono', monospace" }}>
              {item.title}
            </h2>

            {/* Meta row */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <div className="flex items-center gap-1.5">
                <Globe className="h-3 w-3" style={{ color: '#6b7280' }} />
                <span className="text-xs font-medium" style={{ color: '#9ca3af' }}>
                  {post ? post.display_name : item.source_name}
                </span>
              </div>
              <span style={{ color: '#374151' }}>·</span>
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3" style={{ color: '#6b7280' }} />
                <span className="text-xs" style={{ color: '#6b7280' }}>
                  {timeAgo(item.published_at)}
                </span>
              </div>
              {!isPost && (
                <>
                  <span style={{ color: '#374151' }}>·</span>
                  <span className="text-xs" style={{ color: '#6b7280' }}>{item.source_name}</span>
                </>
              )}
            </div>

            {/* Description */}
            {description && (
              <p
                className="text-sm leading-relaxed whitespace-pre-line"
                style={{ color: '#d1d5db', borderLeft: `2px solid ${catColor}40`, paddingLeft: '0.875rem' }}
              >
                {description}
              </p>
            )}
          </div>
        </div>

        {/* Footer CTA */}
        <div
          className="shrink-0 px-5 py-3"
          style={{ borderTop: '1px solid rgba(55,65,81,0.4)', background: 'rgba(17,24,39,0.6)' }}
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-opacity hover:opacity-90"
            style={{ background: catColor, color: '#000' }}
          >
            <ExternalLink className="h-4 w-4" />
            {isPost ? 'View Original Post' : 'Read Full Article'}
          </a>
        </div>
      </div>
    </div>
  )
}
