import { useEffect, useRef, useState } from 'react'
import { Camera, ExternalLink, Maximize2, Play, Square, Volume2, VolumeX, X } from 'lucide-react'

interface Stream {
  id: string
  name: string
  country: string
  flag: string
  region: Region
  /** YouTube live stream video ID (permanent for 24/7 channels) */
  ytId: string
  description: string
  tags: string[]
}

type Region = 'All' | 'Middle East' | 'Europe' | 'Americas' | 'Asia-Pacific'

const REGIONS: Region[] = ['All', 'Middle East', 'Europe', 'Americas', 'Asia-Pacific']

/**
 * 22 geopolitical live streams — using PERMANENT live stream video IDs
 * from major 24/7 broadcast news channels. These IDs are stable because
 * the channels maintain the same "live" video permanently.
 *
 * Sources: Al Jazeera, France 24, DW, NHK, TRT, Euronews, Sky News, etc.
 */
const STREAMS: Stream[] = [
  // ── Middle East ───────────────────────────────────────────────────────────
  {
    id: 'aljazeera-en',
    name: 'Al Jazeera English',
    country: 'QA', flag: '📡', region: 'Middle East',
    ytId: 'aTzW3tqeHpA',
    description: 'Breaking news · Middle East focus',
    tags: ['news', 'conflict', 'middle-east'],
  },
  {
    id: 'trt-world',
    name: 'TRT World',
    country: 'TR', flag: '🇹🇷', region: 'Middle East',
    ytId: 'tshC8jLKZUA',
    description: 'Turkish international · MENA region',
    tags: ['news', 'turkey', 'middle-east'],
  },
  {
    id: 'i24-news',
    name: 'i24 NEWS English',
    country: 'IL', flag: '🇮🇱', region: 'Middle East',
    ytId: 'XFBcoTRoVXA',
    description: 'Israel · Gaza · Live updates',
    tags: ['news', 'israel', 'gaza'],
  },
  {
    id: 'iran-int',
    name: 'Iran International',
    country: 'IR', flag: '🇮🇷', region: 'Middle East',
    ytId: 'bVdBMRkBEss',
    description: 'Iran news · Persian/English',
    tags: ['news', 'iran'],
  },
  {
    id: 'al-arabiya',
    name: 'Al Arabiya English',
    country: 'AE', flag: '🇦🇪', region: 'Middle East',
    ytId: 'XYGY5C9G7rk',
    description: 'Gulf region · Arabic world news',
    tags: ['news', 'gulf', 'arabic'],
  },
  // ── Europe ────────────────────────────────────────────────────────────────
  {
    id: 'france24-en',
    name: 'France 24 English',
    country: 'FR', flag: '🇫🇷', region: 'Europe',
    ytId: 'l8PMl7tUDIE',
    description: 'French international · Europe/Africa',
    tags: ['news', 'france', 'europe'],
  },
  {
    id: 'dw-news',
    name: 'DW News',
    country: 'DE', flag: '🇩🇪', region: 'Europe',
    ytId: 'nSOn_NyW_0c',
    description: 'Deutsche Welle · European affairs',
    tags: ['news', 'germany', 'europe'],
  },
  {
    id: 'sky-news',
    name: 'Sky News',
    country: 'GB', flag: '🇬🇧', region: 'Europe',
    ytId: '9Auq9mYxFEE',
    description: 'UK breaking news · 24/7 live',
    tags: ['news', 'uk', 'europe'],
  },
  {
    id: 'euronews',
    name: 'Euronews',
    country: 'EU', flag: '🇪🇺', region: 'Europe',
    ytId: 'R5xRrBm6Yc0',
    description: 'Pan-European news · 24 languages',
    tags: ['news', 'eu', 'europe'],
  },
  {
    id: 'freedom-ukraine',
    name: 'FREEДOM Ukraine',
    country: 'UA', flag: '🇺🇦', region: 'Europe',
    ytId: 'U3DtV3-jv2w',
    description: 'Ukraine war · Live coverage',
    tags: ['news', 'ukraine', 'war'],
  },
  {
    id: 'bbc-news',
    name: 'BBC News',
    country: 'GB', flag: '🇬🇧', region: 'Europe',
    ytId: 'w_Ma8oQLmSM',
    description: 'BBC World Service · Live',
    tags: ['news', 'uk', 'bbc'],
  },
  // ── Americas ──────────────────────────────────────────────────────────────
  {
    id: 'bloomberg',
    name: 'Bloomberg TV',
    country: 'US', flag: '🇺🇸', region: 'Americas',
    ytId: 'dp8PhLsUcFE',
    description: 'Markets · Finance · Global business',
    tags: ['finance', 'markets', 'us'],
  },
  {
    id: 'cspan',
    name: 'C-SPAN',
    country: 'US', flag: '🇺🇸', region: 'Americas',
    ytId: 'oS7hZlnEiDU',
    description: 'US Congress · Washington DC',
    tags: ['politics', 'us', 'congress'],
  },
  {
    id: 'pbs-newshour',
    name: 'PBS NewsHour',
    country: 'US', flag: '🇺🇸', region: 'Americas',
    ytId: 'fFaKFvqGl8E',
    description: 'US public broadcasting · Live',
    tags: ['news', 'us'],
  },
  {
    id: 'telesur',
    name: 'teleSUR English',
    country: 'VE', flag: '🌎', region: 'Americas',
    ytId: 'RsaHe2zbxaM',
    description: 'Latin America · Investigative',
    tags: ['news', 'latam'],
  },
  // ── Asia-Pacific ──────────────────────────────────────────────────────────
  {
    id: 'nhk-world',
    name: 'NHK World Japan',
    country: 'JP', flag: '🇯🇵', region: 'Asia-Pacific',
    ytId: 'w3OCyZfKd4c',
    description: 'Japan public TV · Asia Pacific',
    tags: ['news', 'japan', 'asia'],
  },
  {
    id: 'cgtn',
    name: 'CGTN',
    country: 'CN', flag: '🇨🇳', region: 'Asia-Pacific',
    ytId: 'vLBGKLFDPRk',
    description: 'China Global Television · 24/7',
    tags: ['news', 'china', 'asia'],
  },
  {
    id: 'arirang',
    name: 'Arirang News',
    country: 'KR', flag: '🇰🇷', region: 'Asia-Pacific',
    ytId: 'zs6dFKlyCgk',
    description: 'South Korea international',
    tags: ['news', 'korea', 'asia'],
  },
  {
    id: 'ndtv',
    name: 'NDTV 24x7',
    country: 'IN', flag: '🇮🇳', region: 'Asia-Pacific',
    ytId: 'bDI67G2YaA8',
    description: 'India news · South Asia',
    tags: ['news', 'india', 'asia'],
  },
  {
    id: 'cna',
    name: 'CNA International',
    country: 'SG', flag: '🇸🇬', region: 'Asia-Pacific',
    ytId: 'DfBDGGfHGs8',
    description: 'Channel NewsAsia · SE Asia',
    tags: ['news', 'singapore', 'asean'],
  },
  {
    id: 'abc-australia',
    name: 'ABC News Australia',
    country: 'AU', flag: '🇦🇺', region: 'Asia-Pacific',
    ytId: 'hgVnmn4vHXw',
    description: 'Australian Broadcasting · Pacific',
    tags: ['news', 'australia', 'pacific'],
  },
  {
    id: 'taiwan-pts',
    name: 'Taiwan PTS Live',
    country: 'TW', flag: '🇹🇼', region: 'Asia-Pacific',
    ytId: 'z4FBj4DVuEk',
    description: 'Taiwan public broadcaster',
    tags: ['news', 'taiwan', 'asia'],
  },
]

// ── Stream tile ─────────────────────────────────────────────────────────────

function StreamTile({ stream, onExpand }: { stream: Stream; onExpand: (s: Stream) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [loaded, setLoaded] = useState(false)
  const [muted, setMuted] = useState(true)
  const [active, setActive] = useState(false)
  const [errored, setErrored] = useState(false)
  const inactiveTimer = useRef<ReturnType<typeof setTimeout>>()

  // Intersection Observer — lazy activate on scroll
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setActive(true); obs.disconnect() } },
      { rootMargin: '120px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Auto-pause after 5 min to save bandwidth
  useEffect(() => {
    if (!active) return
    inactiveTimer.current = setTimeout(() => setActive(false), 5 * 60_000)
    return () => clearTimeout(inactiveTimer.current)
  }, [active])

  // Pause when browser tab hidden
  useEffect(() => {
    const h = () => { if (document.hidden) setActive(false) }
    document.addEventListener('visibilitychange', h)
    return () => document.removeEventListener('visibilitychange', h)
  }, [])

  const embedUrl = `https://www.youtube-nocookie.com/embed/${stream.ytId}?autoplay=1&mute=${muted ? 1 : 0}&controls=0&playsinline=1&rel=0&modestbranding=1&iv_load_policy=3`
  const ytSearchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(stream.name + ' live stream')}&sp=EgJAAQ%3D%3D`

  const handleError = () => { setErrored(true); setLoaded(true) }

  return (
    <div
      ref={ref}
      className="group relative overflow-hidden rounded-lg"
      style={{ background: '#0d1117', border: '1px solid rgba(55,65,81,0.4)', aspectRatio: '16/9' }}
    >
      {active && !errored ? (
        <>
          <iframe
            src={embedUrl}
            allow="autoplay; encrypted-media"
            allowFullScreen
            className="absolute inset-0 h-full w-full"
            style={{ border: 'none' }}
            onLoad={() => setLoaded(true)}
            onError={handleError}
            title={`${stream.name} Live`}
          />
          {!loaded && (
            <div className="absolute inset-0 flex items-center justify-center" style={{ background: '#0d1117' }}>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: '#10b981' }} />
            </div>
          )}
          {/* Hover controls */}
          <div
            className="absolute bottom-0 left-0 right-0 flex items-center gap-1 px-2 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.9))' }}
          >
            <span className="text-[10px] font-bold truncate" style={{ color: '#10b981' }}>
              {stream.flag} {stream.name}
            </span>
            <div className="ml-auto flex shrink-0 gap-1">
              <button onClick={() => setMuted((m) => !m)} className="rounded p-0.5 hover:bg-white/20" title={muted ? 'Unmute' : 'Mute'}>
                {muted ? <VolumeX className="h-3 w-3" style={{ color: '#9ca3af' }} /> : <Volume2 className="h-3 w-3" style={{ color: '#10b981' }} />}
              </button>
              <button onClick={() => { setActive(false); setLoaded(false); setErrored(false) }} className="rounded p-0.5 hover:bg-white/20" title="Stop">
                <Square className="h-3 w-3" style={{ color: '#9ca3af' }} />
              </button>
              <button onClick={() => onExpand(stream)} className="rounded p-0.5 hover:bg-white/20" title="Expand">
                <Maximize2 className="h-3 w-3" style={{ color: '#9ca3af' }} />
              </button>
            </div>
          </div>
        </>
      ) : errored ? (
        /* Stream unavailable fallback */
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3">
          <p className="text-[10px] font-semibold text-center" style={{ color: '#9ca3af' }}>{stream.flag} {stream.name}</p>
          <p className="text-[9px] text-center" style={{ color: '#4b5563' }}>Stream temporarily unavailable</p>
          <a
            href={ytSearchUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded px-2 py-1 text-[9px] font-bold transition-colors"
            style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444' }}
          >
            <ExternalLink className="h-2.5 w-2.5" />
            Search on YouTube
          </a>
        </div>
      ) : (
        /* Play button */
        <button
          className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 w-full transition-colors hover:bg-white/5"
          onClick={() => { setLoaded(false); setErrored(false); setActive(true) }}
        >
          <div
            className="flex h-8 w-8 items-center justify-center rounded-full"
            style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.35)' }}
          >
            <Play className="h-3.5 w-3.5 ml-0.5" style={{ color: '#10b981' }} />
          </div>
          <div className="text-center px-2">
            <p className="text-[11px] font-semibold" style={{ color: '#d1d5db' }}>{stream.flag} {stream.name}</p>
            <p className="text-[9px]" style={{ color: '#4b5563' }}>{stream.description}</p>
          </div>
        </button>
      )}

      {/* LIVE badge */}
      <div className="absolute top-1.5 left-1.5 flex items-center gap-1 rounded px-1 py-0.5 pointer-events-none" style={{ background: 'rgba(0,0,0,0.75)' }}>
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: '#ef4444', animation: 'wm-ping 2s infinite' }} />
        <span className="text-[8px] font-bold tracking-widest" style={{ color: '#ef4444' }}>LIVE</span>
      </div>
    </div>
  )
}

// ── Fullscreen modal ────────────────────────────────────────────────────────

function ExpandedModal({ stream, onClose }: { stream: Stream; onClose: () => void }) {
  const [muted, setMuted] = useState(false)
  const src = `https://www.youtube-nocookie.com/embed/${stream.ytId}?autoplay=1&mute=${muted ? 1 : 0}&controls=1&playsinline=1&rel=0&modestbranding=1`

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.93)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl rounded-xl overflow-hidden shadow-2xl"
        style={{ aspectRatio: '16/9', border: '1px solid rgba(55,65,81,0.6)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <iframe
          src={src}
          allow="autoplay; encrypted-media; fullscreen"
          allowFullScreen
          className="absolute inset-0 h-full w-full"
          style={{ border: 'none' }}
          title={`${stream.name} — Expanded`}
        />
        <div className="absolute top-3 right-3 flex gap-2">
          <button onClick={() => setMuted((m) => !m)} className="rounded-lg p-2" style={{ background: 'rgba(0,0,0,0.75)' }}>
            {muted ? <VolumeX className="h-4 w-4" style={{ color: '#9ca3af' }} /> : <Volume2 className="h-4 w-4" style={{ color: '#10b981' }} />}
          </button>
          <button onClick={onClose} className="rounded-lg p-2" style={{ background: 'rgba(0,0,0,0.75)' }}>
            <X className="h-4 w-4" style={{ color: '#9ca3af' }} />
          </button>
        </div>
        <div className="absolute bottom-4 left-4 pointer-events-none">
          <p className="text-xl font-bold" style={{ color: '#f9fafb', textShadow: '0 2px 10px rgba(0,0,0,0.9)' }}>
            {stream.flag} {stream.name}
          </p>
          <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>{stream.description}</p>
        </div>
      </div>
    </div>
  )
}

// ── Main panel ─────────────────────────────────────────────────────────────

export function LiveCamerasPanel() {
  const [region, setRegion] = useState<Region>('All')
  const [expanded, setExpanded] = useState<Stream | null>(null)

  const filtered = region === 'All' ? STREAMS : STREAMS.filter((s) => s.region === region)

  return (
    <div className="flex h-full flex-col" style={{ background: '#0a0b0d' }}>
      {/* Header */}
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2" style={{ borderColor: 'rgba(55,65,81,0.4)' }}>
        <Camera className="h-3.5 w-3.5" style={{ color: '#10b981' }} />
        <span className="text-xs font-bold tracking-widest" style={{ color: '#f9fafb' }}>LIVE FEEDS</span>
        <div className="flex items-center gap-1 ml-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: '#ef4444', animation: 'wm-ping 2s infinite' }} />
          <span className="text-[9px]" style={{ color: '#ef4444' }}>{STREAMS.length} CHANNELS</span>
        </div>
        <div className="ml-auto text-[9px]" style={{ color: '#4b5563' }}>
          Click to play · Hover for controls
        </div>
      </div>

      {/* Region tabs */}
      <div className="flex shrink-0 gap-0.5 overflow-x-auto px-2 py-1.5 border-b" style={{ borderColor: 'rgba(55,65,81,0.3)' }}>
        {REGIONS.map((r) => {
          const count = r === 'All' ? STREAMS.length : STREAMS.filter((s) => s.region === r).length
          return (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className="shrink-0 rounded px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide transition-colors"
              style={{
                background: region === r ? '#10b981' : 'rgba(31,41,55,0.5)',
                color: region === r ? '#000' : '#6b7280',
              }}
            >
              {r === 'All' ? `ALL (${count})` : `${r.split('-')[0].trim().split(' ')[0]} (${count})`}
            </button>
          )
        })}
      </div>

      {/* Stream grid */}
      <div className="flex-1 overflow-y-auto p-2">
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          {filtered.map((s) => (
            <StreamTile key={s.id} stream={s} onExpand={setExpanded} />
          ))}
        </div>
      </div>

      {expanded && <ExpandedModal stream={expanded} onClose={() => setExpanded(null)} />}
    </div>
  )
}
