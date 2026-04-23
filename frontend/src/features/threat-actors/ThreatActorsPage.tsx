import { useState, useCallback, useMemo } from 'react'
import { Shield, Target, Globe, AlertTriangle, Search, Filter } from 'lucide-react'
import { useThreatActors } from './hooks'
import { ThreatActorCard } from './components/ThreatActorCard'
import { ThreatActorDetail } from './components/ThreatActorDetail'
import type { ThreatActor, ThreatActorFilters, ThreatActorMotivation, ThreatActorSophistication } from './types'

const MOTIVATIONS: Array<{ value: ThreatActorMotivation | ''; label: string }> = [
  { value: '', label: 'All Motivations' },
  { value: 'financial', label: 'Financial' },
  { value: 'espionage', label: 'Espionage' },
  { value: 'hacktivism', label: 'Hacktivism' },
  { value: 'sabotage', label: 'Sabotage' },
]

const SOPHISTICATIONS: Array<{ value: ThreatActorSophistication | ''; label: string }> = [
  { value: '', label: 'All Levels' },
  { value: 'nation-state', label: 'Nation-State' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const COUNTRIES = [
  { value: '', label: 'All Countries' },
  { value: 'RU', label: '🇷🇺 Russia' },
  { value: 'KP', label: '🇰🇵 North Korea' },
  { value: 'CN', label: '🇨🇳 China' },
  { value: 'IR', label: '🇮🇷 Iran' },
  { value: 'GB', label: '🇬🇧 United Kingdom' },
  { value: 'UA', label: '🇺🇦 Ukraine' },
  { value: 'US', label: '🇺🇸 United States' },
]

function selectStyle(): React.CSSProperties {
  return {
    background: 'var(--bg-surface)',
    borderColor: 'var(--border-subtle)',
    color: 'var(--text-primary)',
  }
}

export function ThreatActorsPage() {
  const [search, setSearch] = useState('')
  const [motivation, setMotivation] = useState<ThreatActorMotivation | ''>('')
  const [sophistication, setSophistication] = useState<ThreatActorSophistication | ''>('')
  const [country, setCountry] = useState('')
  const [selectedActor, setSelectedActor] = useState<ThreatActor | null>(null)

  const filters = useMemo<ThreatActorFilters>(
    () => ({
      motivation: motivation || undefined,
      sophistication: sophistication || undefined,
      origin_country: country || undefined,
      search: search || undefined,
    }),
    [motivation, sophistication, country, search],
  )

  const { data: actors = [], isLoading, isError } = useThreatActors(filters)

  const handleSelect = useCallback((actor: ThreatActor) => {
    setSelectedActor((prev) => (prev?.id === actor.id ? null : actor))
  }, [])

  const handleClose = useCallback(() => setSelectedActor(null), [])

  const nationStateCount = actors.filter((a) => a.sophistication === 'nation-state').length
  const activeThisYear = actors.filter((a) => a.last_seen === '2024').length

  return (
    <div className="flex h-full flex-col gap-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5" style={{ color: 'var(--brand-500)' }} />
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Threat Actor Intelligence
          </h1>
        </div>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Aggregated threat intelligence from ThreatFox, OTX, and curated OSINT sources
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            icon: <Shield className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />,
            label: 'Total actors',
            value: actors.length,
          },
          {
            icon: <AlertTriangle className="h-4 w-4" style={{ color: 'var(--danger-400)' }} />,
            label: 'Nation-state',
            value: nationStateCount,
          },
          {
            icon: <Target className="h-4 w-4" style={{ color: 'var(--warning-500)' }} />,
            label: 'Active this year',
            value: activeThisYear,
          },
        ].map(({ icon, label, value }) => (
          <div
            key={label}
            className="flex items-center gap-3 rounded-lg border px-4 py-3"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          >
            {icon}
            <div>
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {label}
              </p>
              <p className="text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {isLoading ? '—' : value}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div
        className="flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      >
        <Filter className="h-4 w-4 shrink-0" style={{ color: 'var(--text-tertiary)' }} />

        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
            style={{ color: 'var(--text-tertiary)' }}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search actors or aliases…"
            className="w-full rounded-md border py-1.5 pl-8 pr-3 text-xs outline-none transition-colors focus:ring-1 focus:ring-brand-500/50"
            style={selectStyle()}
          />
        </div>

        {/* Motivation filter */}
        <select
          value={motivation}
          onChange={(e) => setMotivation(e.target.value as ThreatActorMotivation | '')}
          className="rounded-md border px-3 py-1.5 text-xs outline-none"
          style={selectStyle()}
          aria-label="Filter by motivation"
        >
          {MOTIVATIONS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>

        {/* Sophistication filter */}
        <select
          value={sophistication}
          onChange={(e) => setSophistication(e.target.value as ThreatActorSophistication | '')}
          className="rounded-md border px-3 py-1.5 text-xs outline-none"
          style={selectStyle()}
          aria-label="Filter by sophistication"
        >
          {SOPHISTICATIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        {/* Country filter */}
        <select
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-xs outline-none"
          style={selectStyle()}
          aria-label="Filter by country"
        >
          {COUNTRIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>

        {(search || motivation || sophistication || country) && (
          <button
            onClick={() => {
              setSearch('')
              setMotivation('')
              setSophistication('')
              setCountry('')
            }}
            className="text-xs transition-colors hover:underline"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Main content */}
      {isError && (
        <div
          className="rounded-lg border px-4 py-3 text-sm"
          style={{
            background: 'var(--bg-surface)',
            borderColor: 'var(--border-subtle)',
            color: 'var(--danger-400)',
          }}
        >
          Failed to load threat actor data. Please try again.
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-lg border"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
            />
          ))}
        </div>
      )}

      {!isLoading && !isError && (
        <div
          className={`flex gap-6 ${selectedActor ? 'flex-col lg:flex-row' : ''}`}
        >
          {/* Actor grid */}
          <div
            className={`${
              selectedActor
                ? 'lg:w-[55%] grid grid-cols-1 gap-4 sm:grid-cols-2 content-start'
                : 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3'
            }`}
          >
            {actors.length === 0 ? (
              <div
                className="col-span-full flex flex-col items-center gap-3 rounded-lg border py-16 text-center"
                style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
              >
                <Globe className="h-8 w-8" style={{ color: 'var(--text-tertiary)' }} />
                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  No threat actors match the current filters
                </p>
              </div>
            ) : (
              actors.map((actor) => (
                <ThreatActorCard
                  key={actor.id}
                  actor={actor}
                  selected={selectedActor?.id === actor.id}
                  onSelect={handleSelect}
                />
              ))
            )}
          </div>

          {/* Detail panel */}
          {selectedActor && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-200 lg:w-[45%] lg:sticky lg:top-6 lg:self-start lg:max-h-[calc(100vh-10rem)] lg:overflow-hidden">
              <ThreatActorDetail actor={selectedActor} onClose={handleClose} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
