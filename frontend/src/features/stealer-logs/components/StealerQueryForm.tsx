import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useQueryStealerLogs } from '../hooks'
import type { StealerLogCheck } from '../types'

interface Props {
  onSuccess: (result: StealerLogCheck) => void
}

const QUERY_TYPES = [
  { value: 'email', label: 'Email Address' },
  { value: 'domain', label: 'Domain' },
  { value: 'ip', label: 'IP Address' },
]

export function StealerQueryForm({ onSuccess }: Props) {
  const [query, setQuery] = useState('')
  const [queryType, setQueryType] = useState('email')
  const mutation = useQueryStealerLogs()

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return
    mutation.mutate({ query: query.trim(), queryType }, { onSuccess })
  }, [query, queryType, mutation, onSuccess])

  const errorMessage = mutation.error?.message

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <div className="w-40 shrink-0">
          <label htmlFor="query-type" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Type</label>
          <select
            id="query-type"
            value={queryType}
            onChange={(e) => setQueryType(e.target.value)}
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          >
            {QUERY_TYPES.map((t) => (
              <option key={t.value} value={t.value} style={{ background: 'var(--bg-surface)' }}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="stealer-query" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Query</label>
          <input
            id="stealer-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
            placeholder={queryType === 'email' ? 'user@example.com' : queryType === 'domain' ? 'example.com' : '1.2.3.4'}
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          />
        </div>
      </div>

      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Checks Hudson Rock Cavalier for infostealer compromise records (LummaC2, RedLine, Vidar, etc.)
      </p>

      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <Button onClick={handleSubmit} disabled={!query.trim()} loading={mutation.isPending} className="w-full" size="lg">
        Check Stealer Logs
      </Button>
    </div>
  )
}
