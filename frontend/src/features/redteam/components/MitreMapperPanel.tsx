import { useState, useCallback } from 'react'
import { Map, AlertCircle, ExternalLink, ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { Button } from '@/shared/components/Button'
import { LoadingSpinner } from '@/shared/components/LoadingSpinner'
import { useMitreTechniqueMapper } from '../hooks'
import type { MitreMappingResult, MitreMapping } from '../types'

const ATT_AND_CK_BASE = 'https://attack.mitre.org/techniques/'

function TechniqueCard({ mapping }: { mapping: MitreMapping }) {
  return (
    <div
      className="rounded-lg border p-3 transition-all"
      style={{
        borderColor: mapping.executed ? 'var(--brand-500)' : 'var(--border-subtle)',
        background: mapping.executed ? 'var(--brand-900)' : 'var(--bg-overlay)',
      }}
      aria-label={`Technique ${mapping.techniqueId}: ${mapping.techniqueName}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold" style={{ color: 'var(--brand-400)' }}>
              {mapping.techniqueId}
            </span>
            <Badge variant="neutral" size="sm">{mapping.tacticName}</Badge>
            {mapping.executed && <Badge variant="brand" size="sm" dot>Executed</Badge>}
          </div>
          <p className="mt-0.5 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            {mapping.techniqueName}
          </p>
          {mapping.description && (
            <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {mapping.description}
            </p>
          )}
        </div>
        <a
          href={`${ATT_AND_CK_BASE}${mapping.techniqueId.replace('.', '/')}`}
          target="_blank"
          rel="noreferrer noopener"
          className="shrink-0 rounded p-1 transition-opacity hover:opacity-70"
          style={{ color: 'var(--text-tertiary)' }}
          aria-label={`Open ${mapping.techniqueId} on MITRE ATT&CK website`}
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>
    </div>
  )
}

function ResultsView({ result }: { result: MitreMappingResult }) {
  const tacticsWithTechniques = result.coveredTactics.map((tactic) => ({
    tactic,
    techniques: result.techniques.filter((t) => t.tacticName === tactic),
  }))

  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="brand">{result.totalTechniques} techniques mapped</Badge>
        <Badge variant="neutral">{result.coveredTactics.length} tactics covered</Badge>
      </div>

      <div className="space-y-3">
        {tacticsWithTechniques.map(({ tactic, techniques }) => (
          <div key={tactic}>
            <div className="mb-1.5 flex items-center gap-1.5">
              <ChevronRight className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
              <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                {tactic}
              </h3>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {techniques.map((t) => (
                <TechniqueCard key={t.techniqueId} mapping={t} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function MitreMapperPanel() {
  const [input, setInput] = useState('')
  const [result, setResult] = useState<MitreMappingResult | null>(null)

  const mutation = useMitreTechniqueMapper()

  const handleSubmit = useCallback(() => {
    const techniques = input
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter((t) => /^T\d{4}(\.\d{3})?$/.test(t))

    if (techniques.length === 0) return
    mutation.mutate(techniques, { onSuccess: setResult })
  }, [input, mutation])

  const parsedCount = input
    .split(',')
    .map((t) => t.trim().toUpperCase())
    .filter((t) => /^T\d{4}(\.\d{3})?$/.test(t)).length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Map className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>MITRE ATT&CK Technique Mapper</h2>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <div>
          <label htmlFor="mitre-techniques" className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Technique IDs (comma-separated)
          </label>
          <textarea
            id="mitre-techniques"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="T1078, T1110, T1566, T1059..."
            rows={3}
            className="w-full resize-y rounded-lg border bg-transparent px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
            aria-label="MITRE ATT&CK technique IDs"
          />
          <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {parsedCount > 0
              ? `${parsedCount} valid technique ID${parsedCount !== 1 ? 's' : ''} detected`
              : 'Enter technique IDs like T1078, T1110.001, etc.'}
          </p>
        </div>

        {mutation.error && (
          <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{mutation.error.message}</span>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={parsedCount === 0}
          loading={mutation.isPending}
          className="w-full"
        >
          Map Techniques
        </Button>

        {mutation.isPending && <LoadingSpinner size="sm" className="py-2" />}

        {result && <ResultsView result={result} />}
      </CardBody>
    </Card>
  )
}
