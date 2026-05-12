/**
 * MapPlaceholder — occupies the map slot until deck.gl integration (step 4).
 * Renders a stylised dark canvas with a grid overlay and a status badge.
 */
import { Map } from 'lucide-react'

interface MapPlaceholderProps {
  eventCount?: number
}

export function MapPlaceholder({ eventCount = 0 }: MapPlaceholderProps) {
  return (
    <div
      className="relative flex h-full min-h-[360px] w-full items-center justify-center overflow-hidden rounded-lg border"
      style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}
      role="img"
      aria-label="Map — coming in step 4"
    >
      {/* Grid overlay */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full opacity-10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <pattern id="wm-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#wm-grid)" />
      </svg>

      {/* Fake continent silhouettes — purely decorative */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full opacity-5"
        viewBox="0 0 800 400"
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Rough continent blobs */}
        <ellipse cx="200" cy="160" rx="120" ry="70" fill="currentColor" />
        <ellipse cx="200" cy="260" rx="70" ry="90" fill="currentColor" />
        <ellipse cx="420" cy="150" rx="90" ry="60" fill="currentColor" />
        <ellipse cx="530" cy="200" rx="50" ry="40" fill="currentColor" />
        <ellipse cx="600" cy="160" rx="80" ry="55" fill="currentColor" />
        <ellipse cx="680" cy="240" rx="60" ry="50" fill="currentColor" />
        <ellipse cx="310" cy="320" rx="40" ry="50" fill="currentColor" />
      </svg>

      {/* Centre content */}
      <div className="relative flex flex-col items-center gap-3 text-center">
        <Map className="h-10 w-10" style={{ color: 'var(--brand-500)', opacity: 0.6 }} aria-hidden="true" />
        <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          Interactive map — step 4
        </p>
        <p className="max-w-xs text-xs leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
          deck.gl layers: conflict events, news heatmap, active flights, CII choropleth, and correlation arcs
        </p>
      </div>

      {/* Event count badge */}
      {eventCount > 0 && (
        <div
          className="absolute bottom-3 right-3 rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{ background: 'var(--brand-500)', color: '#fff' }}
        >
          {eventCount.toLocaleString()} events
        </div>
      )}
    </div>
  )
}
