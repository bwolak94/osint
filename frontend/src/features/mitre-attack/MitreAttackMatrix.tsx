import { useState, useMemo, useCallback, useRef } from 'react'
import { Search, Download, Maximize2, Minimize2, X } from 'lucide-react'
import { Badge } from '@/shared/components/Badge'
import { Button } from '@/shared/components/Button'
import { MITRE_TACTICS } from './data/tactics'
import { MITRE_TECHNIQUES, getTechniquesByTactic } from './data/techniques'
import type { MitreTechnique, MitreTactic } from './types'

// ─── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  executedTechniques?: string[]
  onTechniqueClick?: (technique: MitreTechnique) => void
  investigationId?: string
}

// ─── Colour helpers ────────────────────────────────────────────────────────────

function cellBackground(executed: boolean, score: number): string {
  if (!executed) return 'var(--bg-overlay)'
  if (score >= 3) return 'var(--brand-600)'
  if (score === 2) return 'var(--brand-500)'
  return 'var(--brand-400)'
}

function cellBorder(executed: boolean): string {
  return executed ? 'var(--brand-500)' : 'var(--border-subtle)'
}

// ─── Technique tooltip/detail panel ───────────────────────────────────────────

interface TechniqueDetailProps {
  technique: MitreTechnique
  tactic: MitreTactic
  executed: boolean
  onClose: () => void
}

function TechniqueDetail({ technique, tactic, executed, onClose }: TechniqueDetailProps) {
  const url = `https://attack.mitre.org/techniques/${technique.id.replace('.', '/')}`

  return (
    <div
      className="rounded-lg border p-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-200"
      style={{ borderColor: 'var(--border-default)', background: 'var(--bg-surface)' }}
      role="dialog"
      aria-label={`Technique details: ${technique.name}`}
      aria-modal="false"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-bold" style={{ color: 'var(--brand-400)' }}>
              {technique.id}
            </span>
            <Badge variant="neutral" size="sm">{tactic.shortName}</Badge>
            {executed && <Badge variant="brand" size="sm" dot>Executed</Badge>}
          </div>
          <h3 className="mt-0.5 text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            {technique.name}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 transition-opacity hover:opacity-70"
          style={{ color: 'var(--text-tertiary)' }}
          aria-label="Close technique details"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        {technique.description}
      </p>

      {technique.platforms.length > 0 && (
        <div>
          <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>Platforms</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {technique.platforms.map((p) => (
              <span
                key={p}
                className="rounded px-1.5 py-0.5 text-xs"
                style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      <a
        href={url}
        target="_blank"
        rel="noreferrer noopener"
        className="inline-flex items-center gap-1.5 text-xs hover:underline"
        style={{ color: 'var(--brand-400)' }}
        aria-label={`View ${technique.id} on MITRE ATT&CK website`}
      >
        View on MITRE ATT&CK ↗
      </a>
    </div>
  )
}

// ─── Single technique cell ─────────────────────────────────────────────────────

interface CellProps {
  technique: MitreTechnique
  tactic: MitreTactic
  executed: boolean
  score: number
  compact: boolean
  isSelected: boolean
  onSelect: (technique: MitreTechnique, tactic: MitreTactic) => void
}

function TechniqueCell({ technique, tactic, executed, score, compact, isSelected, onSelect }: CellProps) {
  const handleClick = useCallback(() => onSelect(technique, tactic), [technique, tactic, onSelect])
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onSelect(technique, tactic)
      }
    },
    [technique, tactic, onSelect],
  )

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className="cursor-pointer rounded border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      style={{
        background: cellBackground(executed, score),
        borderColor: isSelected ? 'var(--brand-300)' : cellBorder(executed),
        padding: compact ? '3px 4px' : '4px 6px',
        minHeight: compact ? '28px' : '40px',
        outline: isSelected ? `2px solid var(--brand-400)` : undefined,
        outlineOffset: isSelected ? '1px' : undefined,
      }}
      title={`${technique.id} — ${technique.name}`}
      aria-label={`${technique.id}: ${technique.name}${executed ? ' (executed)' : ''}`}
      aria-pressed={isSelected}
    >
      <span
        className="block font-mono leading-tight"
        style={{
          color: executed ? '#fff' : 'var(--text-secondary)',
          fontSize: compact ? '10px' : '11px',
          fontWeight: 600,
        }}
      >
        {technique.id}
      </span>
      {!compact && (
        <span
          className="mt-0.5 block leading-tight"
          style={{
            color: executed ? 'rgba(255,255,255,0.85)' : 'var(--text-tertiary)',
            fontSize: '10px',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {technique.name}
        </span>
      )}
    </div>
  )
}

// ─── Tactic column ─────────────────────────────────────────────────────────────

interface ColumnProps {
  tactic: MitreTactic
  techniques: MitreTechnique[]
  executedSet: Set<string>
  scoreMap: Map<string, number>
  compact: boolean
  selectedId: string | null
  onSelect: (technique: MitreTechnique, tactic: MitreTactic) => void
  searchQuery: string
}

function TacticColumn({
  tactic,
  techniques,
  executedSet,
  scoreMap,
  compact,
  selectedId,
  onSelect,
  searchQuery,
}: ColumnProps) {
  const filteredTechniques = useMemo(() => {
    if (!searchQuery) return techniques
    const q = searchQuery.toLowerCase()
    return techniques.filter(
      (t) =>
        t.id.toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q),
    )
  }, [techniques, searchQuery])

  const executedCount = useMemo(
    () => techniques.filter((t) => executedSet.has(t.id)).length,
    [techniques, executedSet],
  )

  return (
    <div className="flex min-w-[140px] flex-col" style={{ flex: '0 0 140px' }}>
      {/* Tactic header */}
      <div
        className="mb-2 rounded-md px-2 py-2 text-center"
        style={{ background: 'var(--bg-overlay)' }}
      >
        <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-primary)' }}>
          {tactic.shortName}
        </p>
        <p className="mt-0.5 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
          {executedCount > 0 && (
            <span style={{ color: 'var(--brand-400)' }}>{executedCount}/</span>
          )}
          {techniques.length}
        </p>
      </div>

      {/* Technique cells */}
      <div className="flex flex-col gap-1">
        {filteredTechniques.map((tech) => (
          <TechniqueCell
            key={tech.id}
            technique={tech}
            tactic={tactic}
            executed={executedSet.has(tech.id)}
            score={scoreMap.get(tech.id) ?? 0}
            compact={compact}
            isSelected={selectedId === tech.id}
            onSelect={onSelect}
          />
        ))}
        {filteredTechniques.length === 0 && searchQuery && (
          <p className="text-center text-[10px] py-2" style={{ color: 'var(--text-tertiary)' }}>
            No match
          </p>
        )}
      </div>
    </div>
  )
}

// ─── Main matrix ───────────────────────────────────────────────────────────────

export function MitreAttackMatrix({ executedTechniques = [], onTechniqueClick, investigationId }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const [compact, setCompact] = useState(false)
  const [selectedTechnique, setSelectedTechnique] = useState<MitreTechnique | null>(null)
  const [selectedTactic, setSelectedTactic] = useState<MitreTactic | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const executedSet = useMemo(() => new Set(executedTechniques), [executedTechniques])

  // Build score map: techniques executed in multiple tactics get higher score
  const scoreMap = useMemo(() => {
    const map = new Map<string, number>()
    executedTechniques.forEach((id) => {
      map.set(id, Math.min(3, (map.get(id) ?? 0) + 1))
    })
    return map
  }, [executedTechniques])

  const columnData = useMemo(
    () =>
      MITRE_TACTICS.map((tactic) => ({
        tactic,
        techniques: getTechniquesByTactic(tactic.id),
      })),
    [],
  )

  const handleSelect = useCallback(
    (technique: MitreTechnique, tactic: MitreTactic) => {
      if (selectedTechnique?.id === technique.id && selectedTactic?.id === tactic.id) {
        setSelectedTechnique(null)
        setSelectedTactic(null)
      } else {
        setSelectedTechnique(technique)
        setSelectedTactic(tactic)
        onTechniqueClick?.(technique)
      }
    },
    [selectedTechnique, selectedTactic, onTechniqueClick],
  )

  const handleExport = useCallback(() => {
    const data = {
      investigationId: investigationId ?? 'unknown',
      exportedAt: new Date().toISOString(),
      executedTechniques,
      techniqueDetails: executedTechniques.map((id) =>
        MITRE_TECHNIQUES.find((t) => t.id === id),
      ).filter(Boolean),
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mitre-mapping-${investigationId ?? 'export'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [executedTechniques, investigationId])

  const totalExecuted = executedSet.size
  const totalTechniques = MITRE_TECHNIQUES.length

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
              style={{ color: 'var(--text-tertiary)' }}
              aria-hidden="true"
            />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search techniques…"
              className="h-8 rounded-lg border bg-transparent pl-8 pr-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)', width: '200px' }}
              aria-label="Search MITRE techniques"
            />
          </div>

          <button
            type="button"
            onClick={() => setCompact((p) => !p)}
            className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-secondary)', background: 'var(--bg-overlay)' }}
            aria-pressed={compact}
            aria-label={compact ? 'Switch to full mode' : 'Switch to compact mode'}
          >
            {compact ? (
              <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Minimize2 className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {compact ? 'Full' : 'Compact'}
          </button>
        </div>

        <div className="flex items-center gap-3">
          {totalExecuted > 0 && (
            <div className="flex items-center gap-2">
              <Badge variant="brand" dot>{totalExecuted} executed</Badge>
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                / {totalTechniques} total
              </span>
            </div>
          )}
          <Button
            size="sm"
            variant="secondary"
            onClick={handleExport}
            leftIcon={<Download className="h-3.5 w-3.5" aria-hidden="true" />}
            disabled={totalExecuted === 0}
          >
            Export JSON
          </Button>
        </div>
      </div>

      {/* Colour legend */}
      <div className="flex flex-wrap items-center gap-4" aria-label="Colour legend">
        {[
          { label: 'Not executed', bg: 'var(--bg-overlay)', border: 'var(--border-subtle)' },
          { label: 'Executed (low)', bg: 'var(--brand-400)', border: 'var(--brand-500)' },
          { label: 'Executed (med)', bg: 'var(--brand-500)', border: 'var(--brand-500)' },
          { label: 'Executed (high)', bg: 'var(--brand-600)', border: 'var(--brand-500)' },
        ].map(({ label, bg, border }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3.5 w-3.5 rounded border"
              style={{ background: bg, borderColor: border }}
              aria-hidden="true"
            />
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Technique detail panel */}
      {selectedTechnique && selectedTactic && (
        <TechniqueDetail
          technique={selectedTechnique}
          tactic={selectedTactic}
          executed={executedSet.has(selectedTechnique.id)}
          onClose={() => { setSelectedTechnique(null); setSelectedTactic(null) }}
        />
      )}

      {/* Scrollable matrix */}
      <div
        ref={scrollRef}
        className="overflow-x-auto rounded-lg border pb-4"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
        role="region"
        aria-label="MITRE ATT&CK Enterprise matrix"
        tabIndex={0}
      >
        <div className="flex gap-2 p-4" style={{ minWidth: 'max-content' }}>
          {columnData.map(({ tactic, techniques }) => (
            <TacticColumn
              key={tactic.id}
              tactic={tactic}
              techniques={techniques}
              executedSet={executedSet}
              scoreMap={scoreMap}
              compact={compact}
              selectedId={selectedTechnique?.id ?? null}
              onSelect={handleSelect}
              searchQuery={searchQuery}
            />
          ))}
        </div>
      </div>

      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Data reference: MITRE ATT&CK® Enterprise v14 —{' '}
        <a
          href="https://attack.mitre.org"
          target="_blank"
          rel="noreferrer noopener"
          className="hover:underline"
          style={{ color: 'var(--brand-400)' }}
        >
          attack.mitre.org
        </a>
      </p>
    </div>
  )
}
