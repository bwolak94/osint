import { useMemo } from 'react'
import type { NewsItem } from '../types'

const CATEGORY_COLORS: Record<string, string> = {
  geopolitics: '#ef4444',
  military:    '#3b82f6',
  cyber:       '#10b981',
  disaster:    '#f97316',
  health:      '#ec4899',
  energy:      '#6366f1',
  economy:     '#eab308',
}

const PRIORITY_CATEGORIES = new Set(['geopolitics', 'military', 'cyber', 'disaster'])

interface BreakingNewsTickerProps {
  /** Latest news items — usually the full feed from useNews. */
  items: NewsItem[]
}

export function BreakingNewsTicker({ items }: BreakingNewsTickerProps) {
  const tickerItems = useMemo(
    () => items.filter((i) => PRIORITY_CATEGORIES.has(i.category)).slice(0, 20),
    [items],
  )

  if (tickerItems.length === 0) return null

  // Duration scales with content so each headline is visible for ~3 s
  const durationS = Math.max(40, tickerItems.length * 4)

  return (
    <div
      className="flex shrink-0 items-center overflow-hidden border-t"
      style={{
        height: 26,
        background: 'rgba(10,11,20,0.97)',
        borderColor: 'rgba(55,65,81,0.35)',
      }}
    >
      {/* LIVE FEED label */}
      <div
        className="flex shrink-0 items-center gap-1.5 border-r px-3 h-full"
        style={{
          background: 'rgba(239,68,68,0.1)',
          borderColor: 'rgba(239,68,68,0.25)',
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: '#ef4444', animation: 'wm-ping 1.5s infinite' }}
        />
        <span
          className="text-[9px] font-black tracking-widest whitespace-nowrap"
          style={{ color: '#ef4444' }}
        >
          LIVE
        </span>
      </div>

      {/* Scrolling marquee — doubled so it loops seamlessly */}
      <div className="relative flex-1 overflow-hidden">
        <div
          style={{
            display: 'flex',
            whiteSpace: 'nowrap',
            animation: `wm-ticker ${durationS}s linear infinite`,
            willChange: 'transform',
          }}
        >
          {[0, 1].map((copy) => (
            <span key={copy} className="inline-flex items-center">
              {tickerItems.map((item, idx) => (
                <span key={`${copy}-${item.id}`} className="inline-flex items-center">
                  {idx > 0 && (
                    <span
                      className="mx-4 text-[8px]"
                      style={{ color: '#374151' }}
                    >
                      ◆
                    </span>
                  )}
                  <span
                    className="text-[8px] font-bold uppercase mr-1.5"
                    style={{ color: CATEGORY_COLORS[item.category] ?? '#6b7280' }}
                  >
                    [{item.category.slice(0, 3).toUpperCase()}]
                  </span>
                  <span className="text-[10px]" style={{ color: '#9ca3af' }}>
                    {item.title}
                  </span>
                </span>
              ))}
              {/* Small gap between copies */}
              <span className="inline-block w-24" />
            </span>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes wm-ticker {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  )
}
