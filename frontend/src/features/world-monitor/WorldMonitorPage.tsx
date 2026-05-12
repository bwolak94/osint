/**
 * WorldMonitorDashboard — Geopolitical intelligence dashboard.
 *
 * Layout:
 *   ┌────────────────────────────────────────────────────────────────────┐
 *   │  TOPBAR: DEFCON · region · UTC clock · live badge · feed count    │
 *   ├──────────────────────────────────────┬───────────────────────────┤
 *   │                                      │                           │
 *   │   Interactive Map (Leaflet)          │  Live News Feed           │
 *   │   + LayerPanel overlay              │  (scrollable)             │
 *   │   + TimeRange selector              │                           │
 *   ├──────────────────────────────────────┴───────────────────────────┤
 *   │  BOTTOM: Map Legend · AI Insights                                 │
 *   └────────────────────────────────────────────────────────────────────┘
 */
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  Globe2, Radio, Clock, ChevronDown, Maximize2, Camera, Rss, Brain, X,
} from 'lucide-react'
import { useWorldMonitorBootstrap, useNews, useWorldMonitorHealth, useMapEvents } from './hooks'
import { ThreatIndicator } from './components/ThreatIndicator'
import { LayerPanel } from './components/LayerPanel'
import { LiveNewsPanel } from './components/LiveNewsPanel'
import { LiveCamerasPanel } from './components/LiveCamerasPanel'
import { AiInsights } from './components/AiInsights'
import { BreakingNewsTicker } from './components/BreakingNewsTicker'
import { LAYER_CONFIGS, MOCK_EVENTS, type LayerKey, type MapEvent } from './mapTypes'
import type { MapEventItem } from './types'

type RightPanel = 'news' | 'cameras' | 'insights'

// Lazy-load Leaflet map (heavy, contains DOM side effects)
const WorldMap = lazy(() =>
  import('./components/WorldMap').then((m) => ({ default: m.WorldMap }))
)

const TIME_RANGES = ['1h', '6h', '24h', '48h', '7d', 'all'] as const
type TimeRange = (typeof TIME_RANGES)[number]

const REGIONS = ['Global', 'Europe', 'Middle East', 'Asia-Pacific', 'Americas', 'Africa']

function UtcClock() {
  const [time, setTime] = useState(() => new Date().toUTCString().slice(17, 25))
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toUTCString().slice(17, 25)), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="flex items-center gap-1.5">
      <Clock className="h-3.5 w-3.5" style={{ color: '#6b7280' }} />
      <span className="font-mono text-xs" style={{ color: '#9ca3af' }}>
        {new Date().toUTCString().slice(0, 16)} {time} UTC
      </span>
    </div>
  )
}

/** Convert a MapEventItem from the API to the MapEvent format used by WorldMap. */
function toMapEvent(item: MapEventItem): MapEvent {
  const validLayers = new Set<LayerKey>([
    'conflict', 'intel', 'military', 'nuclear', 'cyber', 'crisis', 'energy', 'disaster',
  ])
  const layer: LayerKey = validLayers.has(item.layer as LayerKey)
    ? (item.layer as LayerKey)
    : 'crisis'
  return {
    id: item.id,
    layer,
    lat: item.lat,
    lng: item.lng,
    title: item.title,
    severity: item.severity,
    timestamp: item.timestamp,
  }
}

export function WorldMonitorDashboard() {
  const { data: bootstrap } = useWorldMonitorBootstrap()
  const { data: health } = useWorldMonitorHealth()
  const { data: newsData } = useNews(null, 1, 100)
  const { data: eventsData } = useMapEvents()

  const [activeLayers, setActiveLayers] = useState<Set<LayerKey>>(
    new Set(LAYER_CONFIGS.map((l) => l.key))
  )
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const [region, setRegion] = useState('Global')
  const [mapFullscreen, setMapFullscreen] = useState(false)
  const [rightPanel, setRightPanel] = useState<RightPanel>('news')

  // Live event alerts — show popup for new high-severity map events
  const [alertQueue, setAlertQueue] = useState<MapEvent[]>([])
  const seenEventIds = useRef(new Set<string>())

  const totalCached = bootstrap?.news?.total_cached ?? 0
  const latestNews = newsData?.items ?? bootstrap?.news?.items ?? []

  // Alert on new high-severity events (fires when eventsData changes)
  useEffect(() => {
    if (!eventsData?.events) return
    const newAlerts: MapEvent[] = []
    for (const ev of eventsData.events) {
      if (ev.severity === 'high' && !seenEventIds.current.has(ev.id)) {
        seenEventIds.current.add(ev.id)
        newAlerts.push(toMapEvent(ev))
      }
    }
    if (newAlerts.length > 0) {
      setAlertQueue((prev) => [...newAlerts.slice(0, 3), ...prev].slice(0, 5))
    }
  }, [eventsData])

  // Use real events from API; fall back to bootstrap events, then to mock data
  const liveEvents: MapEvent[] = (
    eventsData?.events
    ?? bootstrap?.events?.items
    ?? []
  ).map(toMapEvent)

  const mapEvents: MapEvent[] = liveEvents.length > 0 ? liveEvents : MOCK_EVENTS

  const toggleLayer = useCallback((key: LayerKey) => {
    setActiveLayers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  // Count events per layer for the layer panel badges
  const eventCounts = mapEvents.reduce<Record<LayerKey, number>>(
    (acc, ev) => {
      acc[ev.layer] = (acc[ev.layer] ?? 0) + 1
      return acc
    },
    {} as Record<LayerKey, number>
  )

  const isLive = health?.status === 'OK'

  return (
    <div
      className="flex flex-col"
      style={{
        height: 'calc(100vh - 56px)',
        background: '#0a0b0d',
        color: '#e5e7eb',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      }}
    >
      {/* ── TOP BAR ───────────────────────────────────────────────── */}
      <div
        className="flex shrink-0 items-center gap-3 border-b px-4 py-2"
        style={{ borderColor: 'rgba(55,65,81,0.6)', background: 'rgba(10,11,20,0.95)' }}
      >
        {/* Brand */}
        <div className="flex items-center gap-2">
          <Globe2 className="h-5 w-5" style={{ color: '#10b981' }} />
          <span className="text-sm font-bold tracking-widest" style={{ color: '#f9fafb' }}>
            MONITOR
          </span>
        </div>

        <div className="h-4 w-px" style={{ background: 'rgba(55,65,81,0.6)' }} />

        {/* Live badge */}
        <div className="flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background: isLive ? '#10b981' : '#6b7280',
              boxShadow: isLive ? '0 0 6px #10b981' : 'none',
              animation: isLive ? 'wm-ping 2s infinite' : 'none',
            }}
          />
          <span className="text-[10px] font-semibold tracking-widest" style={{ color: isLive ? '#10b981' : '#6b7280' }}>
            {isLive ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>

        {/* Region selector */}
        <div className="relative">
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className="appearance-none rounded px-2.5 py-1 pr-6 text-xs outline-none"
            style={{ background: 'rgba(31,41,55,0.8)', border: '1px solid rgba(55,65,81,0.6)', color: '#d1d5db', cursor: 'pointer' }}
          >
            {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2" style={{ color: '#6b7280' }} />
        </div>

        <div className="flex-1" />

        {/* UTC Clock */}
        <UtcClock />

        <div className="h-4 w-px" style={{ background: 'rgba(55,65,81,0.6)' }} />

        {/* DEFCON */}
        <ThreatIndicator level={4} />

        <div className="h-4 w-px" style={{ background: 'rgba(55,65,81,0.6)' }} />

        {/* Feed count */}
        <div className="flex items-center gap-1.5">
          <Radio className="h-3.5 w-3.5" style={{ color: '#6b7280' }} />
          <span className="text-xs" style={{ color: '#9ca3af' }}>
            <span style={{ color: '#10b981', fontWeight: 600 }}>{totalCached}</span> articles
          </span>
        </div>
      </div>

      {/* ── MAIN CONTENT ──────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 gap-0">

        {/* Left: Map area */}
        <div
          className="relative flex-1 min-w-0"
          style={{ borderRight: '1px solid rgba(55,65,81,0.4)' }}
        >
          {/* Time range selector */}
          <div
            className="absolute bottom-3 left-1/2 z-[1000] flex -translate-x-1/2 items-center gap-0.5 rounded-md p-0.5"
            style={{ background: 'rgba(10,11,20,0.9)', border: '1px solid rgba(55,65,81,0.6)', backdropFilter: 'blur(8px)' }}
          >
            {TIME_RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className="rounded px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors"
                style={{
                  background: timeRange === r ? '#10b981' : 'transparent',
                  color: timeRange === r ? '#000' : '#6b7280',
                }}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Fullscreen toggle */}
          <button
            onClick={() => setMapFullscreen((v) => !v)}
            className="absolute top-3 right-3 z-[1000] rounded p-1.5 transition-colors hover:bg-white/10"
            style={{ background: 'rgba(10,11,20,0.8)', border: '1px solid rgba(55,65,81,0.5)' }}
            title="Toggle fullscreen"
          >
            <Maximize2 className="h-3.5 w-3.5" style={{ color: '#9ca3af' }} />
          </button>

          {/* Layer panel */}
          <LayerPanel
            activeLayers={activeLayers}
            onToggle={toggleLayer}
            eventCounts={eventCounts}
          />

          {/* Map */}
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center" style={{ background: '#0d1117' }}>
                <div className="text-xs animate-pulse" style={{ color: '#374151' }}>Loading map…</div>
              </div>
            }
          >
            <WorldMap
              events={mapEvents}
              activeLayers={activeLayers}
              timeRange={timeRange}
              region={region}
            />
          </Suspense>

          {/* Legend */}
          <div
            className="absolute bottom-12 right-3 z-[1000] flex flex-wrap gap-x-3 gap-y-1 rounded-md px-3 py-2"
            style={{ background: 'rgba(10,11,20,0.85)', border: '1px solid rgba(55,65,81,0.5)', maxWidth: 280 }}
          >
            {LAYER_CONFIGS.filter((l) => activeLayers.has(l.key)).map((l) => (
              <div key={l.key} className="flex items-center gap-1">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: l.color, boxShadow: `0 0 4px ${l.color}` }}
                />
                <span className="text-[9px] uppercase tracking-wide" style={{ color: '#6b7280' }}>
                  {l.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Tabbed panel column */}
        <div className="flex w-[340px] shrink-0 flex-col">
          {/* Tab selector */}
          <div
            className="flex shrink-0 border-b"
            style={{ borderColor: 'rgba(55,65,81,0.4)', background: 'rgba(10,11,20,0.95)' }}
          >
            {([
              { key: 'news',     label: 'NEWS',    icon: Rss },
              { key: 'cameras',  label: 'CAMERAS', icon: Camera },
              { key: 'insights', label: 'AI',      icon: Brain },
            ] as { key: RightPanel; label: string; icon: React.ElementType }[]).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setRightPanel(key)}
                className="flex flex-1 items-center justify-center gap-1.5 py-2 text-[10px] font-bold tracking-widest transition-colors"
                style={{
                  color: rightPanel === key ? '#10b981' : '#4b5563',
                  borderBottom: rightPanel === key ? '2px solid #10b981' : '2px solid transparent',
                }}
              >
                <Icon className="h-3 w-3" />
                {label}
              </button>
            ))}
          </div>

          {/* Panel content */}
          <div className="min-h-0 flex-1 overflow-hidden">
            {rightPanel === 'news'     && <LiveNewsPanel />}
            {rightPanel === 'cameras'  && <LiveCamerasPanel />}
            {rightPanel === 'insights' && <AiInsights latestNews={latestNews} />}
          </div>
        </div>
      </div>

      {/* ── BREAKING NEWS TICKER ──────────────────────────────────────── */}
      <BreakingNewsTicker items={latestNews} />

      {/* ── HIGH-SEVERITY EVENT ALERTS ────────────────────────────────── */}
      {alertQueue.length > 0 && (
        <div className="pointer-events-none fixed bottom-8 right-4 z-[9000] flex flex-col gap-2">
          {alertQueue.map((alert) => (
            <div
              key={alert.id}
              className="pointer-events-auto flex items-start gap-2.5 rounded-lg px-3 py-2.5 shadow-xl"
              style={{
                background: 'rgba(10,11,20,0.97)',
                border: '1px solid rgba(239,68,68,0.5)',
                maxWidth: 320,
                boxShadow: '0 0 20px rgba(239,68,68,0.15)',
              }}
            >
              <span
                className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
                style={{ background: '#ef4444', animation: 'wm-ping 1.5s infinite', boxShadow: '0 0 6px #ef4444' }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-[9px] font-black tracking-widest mb-0.5" style={{ color: '#ef4444' }}>
                  HIGH SEVERITY EVENT
                </p>
                <p className="text-[11px] leading-snug" style={{ color: '#e5e7eb' }}>{alert.title}</p>
                <p className="text-[9px] mt-0.5" style={{ color: '#6b7280' }}>
                  {alert.layer.toUpperCase()} · {new Date(alert.timestamp).toUTCString().slice(17, 25)} UTC
                </p>
              </div>
              <button
                onClick={() => setAlertQueue((q) => q.filter((a) => a.id !== alert.id))}
                className="shrink-0 rounded p-0.5 hover:bg-white/10 transition-colors"
              >
                <X className="h-3 w-3" style={{ color: '#6b7280' }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Pulse animation */}
      <style>{`
        @keyframes wm-ping {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}

export default WorldMonitorDashboard
