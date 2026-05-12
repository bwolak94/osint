import { useState, useCallback } from 'react'
import { Archive, AlertCircle, CheckCircle, XCircle, Lock, Unlock } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { Button } from '@/shared/components/Button'
import { LoadingSpinner } from '@/shared/components/LoadingSpinner'
import { useCloudHunt } from '../hooks'
import type { CloudHuntResult, BucketResult } from '../types'

const PROVIDERS = ['AWS S3', 'Azure Blob', 'GCP Storage'] as const
type Provider = (typeof PROVIDERS)[number]

const providerKey: Record<Provider, string> = {
  'AWS S3': 'AWS',
  'Azure Blob': 'Azure',
  'GCP Storage': 'GCP',
}

function RiskSummary({ result }: { result: CloudHuntResult }) {
  const pct = result.totalBuckets > 0
    ? Math.round((result.accessibleBuckets / result.totalBuckets) * 100)
    : 0

  const riskVariant =
    pct === 0 ? 'success' : pct < 30 ? 'warning' : 'danger'

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }}>
      <Badge variant={riskVariant} dot>
        {result.accessibleBuckets} / {result.totalBuckets} accessible
      </Badge>
      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        {pct}% exposure rate
      </span>
    </div>
  )
}

function BucketRow({ bucket }: { bucket: BucketResult }) {
  return (
    <tr className="border-b text-xs transition-colors hover:opacity-80" style={{ borderColor: 'var(--border-subtle)' }}>
      <td className="py-2.5 pr-4 font-mono" style={{ color: 'var(--text-primary)' }}>{bucket.name}</td>
      <td className="pr-4">
        <Badge variant="neutral" size="sm">{bucket.provider}</Badge>
      </td>
      <td className="pr-4">
        <a
          href={bucket.url}
          target="_blank"
          rel="noreferrer noopener"
          className="truncate max-w-[180px] block hover:underline"
          style={{ color: 'var(--brand-500)' }}
          aria-label={`Open bucket URL: ${bucket.url}`}
        >
          {bucket.url}
        </a>
      </td>
      <td className="pr-4">
        {bucket.accessible ? (
          <span className="flex items-center gap-1" style={{ color: 'var(--danger-500)' }}>
            <Unlock className="h-3 w-3" aria-hidden="true" />
            Public
          </span>
        ) : (
          <span className="flex items-center gap-1" style={{ color: 'var(--success-500)' }}>
            <Lock className="h-3 w-3" aria-hidden="true" />
            Private
          </span>
        )}
      </td>
      <td style={{ color: 'var(--text-secondary)' }}>{bucket.permissions}</td>
    </tr>
  )
}

function ResultsView({ result }: { result: CloudHuntResult }) {
  return (
    <div className="mt-4 space-y-4">
      <RiskSummary result={result} />
      {result.buckets.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm" style={{ borderColor: 'var(--success-500)', color: 'var(--success-500)', background: 'var(--success-900)' }}>
          <CheckCircle className="h-4 w-4 shrink-0" />
          No exposed buckets found
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--border-subtle)' }}>
          <table className="min-w-full" aria-label="Cloud storage buckets">
            <thead>
              <tr className="border-b text-xs" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }}>
                <th className="py-2 pr-4 text-left font-semibold" style={{ color: 'var(--text-secondary)' }}>Bucket Name</th>
                <th className="py-2 pr-4 text-left font-semibold" style={{ color: 'var(--text-secondary)' }}>Provider</th>
                <th className="py-2 pr-4 text-left font-semibold" style={{ color: 'var(--text-secondary)' }}>URL</th>
                <th className="py-2 pr-4 text-left font-semibold" style={{ color: 'var(--text-secondary)' }}>Access</th>
                <th className="py-2 text-left font-semibold" style={{ color: 'var(--text-secondary)' }}>Permissions</th>
              </tr>
            </thead>
            <tbody>
              {result.buckets.map((b, i) => (
                <BucketRow key={i} bucket={b} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function CloudStorageHunterPanel() {
  const [domain, setDomain] = useState('')
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(
    new Set(['AWS', 'Azure', 'GCP']),
  )
  const [result, setResult] = useState<CloudHuntResult | null>(null)

  const mutation = useCloudHunt()

  const toggleProvider = useCallback((key: string) => {
    setSelectedProviders((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  const handleSubmit = useCallback(() => {
    if (!domain.trim() || selectedProviders.size === 0) return
    mutation.mutate(
      { domain: domain.trim(), providers: Array.from(selectedProviders) },
      { onSuccess: setResult },
    )
  }, [domain, selectedProviders, mutation])

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Archive className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Azure / S3 Cloud Storage Hunter</h2>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <div>
          <label htmlFor="cloud-hunt-domain" className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Target Domain
          </label>
          <input
            id="cloud-hunt-domain"
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
            placeholder="example.com"
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          />
        </div>

        <fieldset>
          <legend className="mb-2 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Cloud Providers</legend>
          <div className="flex flex-wrap gap-3">
            {PROVIDERS.map((p) => {
              const key = providerKey[p]
              const checked = selectedProviders.has(key)
              return (
                <label
                  key={p}
                  className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-all"
                  style={{
                    borderColor: checked ? 'var(--brand-500)' : 'var(--border-subtle)',
                    background: checked ? 'var(--brand-900)' : 'var(--bg-overlay)',
                    color: checked ? 'var(--brand-400)' : 'var(--text-secondary)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleProvider(key)}
                    className="sr-only"
                    aria-label={`Include ${p}`}
                  />
                  <span
                    className="flex h-3.5 w-3.5 items-center justify-center rounded border"
                    style={{
                      borderColor: checked ? 'var(--brand-500)' : 'var(--border-default)',
                      background: checked ? 'var(--brand-500)' : 'transparent',
                    }}
                    aria-hidden="true"
                  >
                    {checked && <XCircle className="h-2.5 w-2.5 text-white" />}
                  </span>
                  {p}
                </label>
              )
            })}
          </div>
        </fieldset>

        {mutation.error && (
          <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{mutation.error.message}</span>
          </div>
        )}

        <Button
          onClick={handleSubmit}
          disabled={!domain.trim() || selectedProviders.size === 0}
          loading={mutation.isPending}
          className="w-full"
        >
          Hunt Cloud Storage
        </Button>

        {mutation.isPending && <LoadingSpinner size="sm" className="py-2" />}

        {result && <ResultsView result={result} />}
      </CardBody>
    </Card>
  )
}
