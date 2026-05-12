import { Brain, TrendingUp, AlertCircle } from 'lucide-react'
import type { NewsItem } from '../types'

const THEATER_DATA = [
  { name: 'Ukraine Theater',  level: 'CRIT', color: '#ef4444', air: 4, sea: 0, trend: '+stable' },
  { name: 'Middle East',      level: 'HIGH', color: '#f97316', air: 2, sea: 2, trend: '+Iran' },
  { name: 'Korean Peninsula', level: 'ELEV', color: '#eab308', air: 1, sea: 1, trend: 'stable' },
  { name: 'Taiwan Strait',    level: 'WATCH',color: '#3b82f6', air: 0, sea: 3, trend: 'stable' },
]

interface AiInsightsProps {
  latestNews: NewsItem[]
}

export function AiInsights({ latestNews }: AiInsightsProps) {
  // Derive a simple "world brief" from the latest high-priority headlines
  const headlines = latestNews
    .filter((n) => ['geopolitics', 'military', 'cyber'].includes(n.category))
    .slice(0, 3)

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex shrink-0 items-center justify-between border-b px-3 py-2"
        style={{ borderColor: 'rgba(55,65,81,0.6)' }}
      >
        <div className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5" style={{ color: '#8b5cf6' }} />
          <span className="text-xs font-semibold tracking-wider" style={{ color: '#e5e7eb' }}>
            AI INSIGHTS
          </span>
        </div>
        <span
          className="rounded-full px-2 py-0.5 text-[9px] font-bold tracking-wider"
          style={{ background: '#10b98120', color: '#10b981', border: '1px solid #10b98140' }}
        >
          LIVE
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 space-y-4" style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
        {/* World Brief */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <AlertCircle className="h-3 w-3" style={{ color: '#6b7280' }} />
            <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: '#6b7280' }}>
              World Brief
            </span>
          </div>
          <div
            className="rounded-md p-2.5 text-xs leading-relaxed space-y-1.5"
            style={{ background: 'rgba(30,40,60,0.6)', border: '1px solid rgba(55,65,81,0.5)', color: '#d1d5db' }}
          >
            {headlines.length > 0 ? (
              headlines.map((item) => (
                <p key={item.id} className="line-clamp-2 text-[11px]" style={{ color: '#9ca3af' }}>
                  • {item.title}
                </p>
              ))
            ) : (
              <p className="text-[11px]" style={{ color: '#6b7280' }}>
                Aggregating intelligence signals...
              </p>
            )}
          </div>
        </div>

        {/* Strategic Posture */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp className="h-3 w-3" style={{ color: '#6b7280' }} />
            <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: '#6b7280' }}>
              Strategic Posture
            </span>
          </div>
          <div className="space-y-1.5">
            {THEATER_DATA.map((t) => (
              <div
                key={t.name}
                className="flex items-center gap-2 rounded px-2.5 py-2"
                style={{ background: 'rgba(20,30,50,0.6)', border: `1px solid ${t.color}25` }}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] font-medium truncate" style={{ color: '#e5e7eb' }}>{t.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    {t.air > 0 && (
                      <span className="text-[9px]" style={{ color: '#9ca3af' }}>✈ {t.air}</span>
                    )}
                    {t.sea > 0 && (
                      <span className="text-[9px]" style={{ color: '#9ca3af' }}>⚓ {t.sea}</span>
                    )}
                    <span className="text-[9px]" style={{ color: '#4b5563' }}>→ {t.trend}</span>
                  </div>
                </div>
                <span
                  className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wider"
                  style={{ background: `${t.color}20`, color: t.color, border: `1px solid ${t.color}40` }}
                >
                  {t.level}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
