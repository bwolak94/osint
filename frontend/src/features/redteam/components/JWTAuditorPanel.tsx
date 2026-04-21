import { useState, useCallback } from 'react'
import { Key, AlertCircle, ChevronDown, ChevronUp, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { Button } from '@/shared/components/Button'
import { LoadingSpinner } from '@/shared/components/LoadingSpinner'
import { useJWTAudit } from '../hooks'
import type { JWTAuditResult, JWTVuln } from '../types'

type SeverityVariant = 'danger' | 'warning' | 'info' | 'neutral'

const severityVariant: Record<JWTVuln['severity'], SeverityVariant> = {
  Critical: 'danger',
  High: 'danger',
  Medium: 'warning',
  Low: 'info',
}

function JSONPreview({ data, label }: { data: Record<string, unknown>; label: string }) {
  const [expanded, setExpanded] = useState(true)
  return (
    <div className="rounded-lg border" style={{ borderColor: 'var(--border-subtle)' }}>
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold transition-colors hover:opacity-80"
        style={{ color: 'var(--text-secondary)' }}
        aria-expanded={expanded}
      >
        <span>{label}</span>
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {expanded && (
        <pre
          className="overflow-x-auto rounded-b-lg px-3 pb-3 text-xs"
          style={{ background: 'var(--bg-overlay)', color: 'var(--text-primary)' }}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

function VulnRow({ vuln }: { vuln: JWTVuln }) {
  return (
    <li className="flex items-start gap-3 rounded-lg border px-3 py-2.5" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }}>
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--danger-500)' }} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{vuln.type}</span>
          <Badge variant={severityVariant[vuln.severity]} size="sm">{vuln.severity}</Badge>
        </div>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>{vuln.description}</p>
      </div>
    </li>
  )
}

function ResultView({ result }: { result: JWTAuditResult }) {
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant="neutral">Algorithm: <strong>{result.algorithm}</strong></Badge>
        <Badge variant={result.noneAlgorithmVulnerable ? 'danger' : 'success'}>
          {result.noneAlgorithmVulnerable ? 'None-Alg: VULNERABLE' : 'None-Alg: Safe'}
        </Badge>
        <Badge variant={result.algorithmConfusionRisk ? 'warning' : 'success'}>
          {result.algorithmConfusionRisk ? 'Alg Confusion: RISK' : 'Alg Confusion: Safe'}
        </Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <JSONPreview data={result.header} label="Header" />
        <JSONPreview data={result.payload} label="Payload" />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Vulnerabilities ({result.vulnerabilities.length})
        </h3>
        {result.vulnerabilities.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm" style={{ borderColor: 'var(--success-500)', color: 'var(--success-500)', background: 'var(--success-900)' }}>
            <ShieldCheck className="h-4 w-4 shrink-0" />
            No vulnerabilities detected
          </div>
        ) : (
          <ul className="space-y-2" role="list" aria-label="JWT vulnerabilities">
            {result.vulnerabilities.map((v, i) => (
              <VulnRow key={i} vuln={v} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function JWTAuditorPanel() {
  const [targetUrl, setTargetUrl] = useState('')
  const [token, setToken] = useState('')
  const [result, setResult] = useState<JWTAuditResult | null>(null)

  const mutation = useJWTAudit()

  const handleSubmit = useCallback(() => {
    if (!targetUrl.trim() && !token.trim()) return
    mutation.mutate(
      { targetUrl: targetUrl.trim(), token: token.trim() || undefined },
      { onSuccess: setResult },
    )
  }, [targetUrl, token, mutation])

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>JWT Security Auditor</h2>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <div>
          <label htmlFor="jwt-target-url" className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Target URL (optional — fetches token from login endpoint)
          </label>
          <input
            id="jwt-target-url"
            type="url"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="https://api.example.com/auth/login"
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          />
        </div>

        <div>
          <label htmlFor="jwt-token" className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            JWT Token (paste directly)
          </label>
          <textarea
            id="jwt-token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            rows={3}
            className="w-full resize-y rounded-lg border bg-transparent px-3 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
            aria-label="JWT token input"
          />
        </div>

        {mutation.error && (
          <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{mutation.error.message}</span>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!targetUrl.trim() && !token.trim()}
          loading={mutation.isPending}
          className="w-full"
        >
          Run JWT Audit
        </Button>

        {mutation.isPending && <LoadingSpinner size="sm" className="py-2" />}

        {result && <ResultView result={result} />}
      </CardBody>
    </Card>
  )
}
