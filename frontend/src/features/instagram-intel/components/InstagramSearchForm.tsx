import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useScanInstagramIntel } from '../hooks'
import type { InstagramIntelScan, QueryType } from '../types'

interface Props {
  onSuccess: (result: InstagramIntelScan) => void
}

const QUERY_TYPE_OPTIONS: { value: QueryType; label: string; placeholder: string }[] = [
  { value: 'username', label: 'Username', placeholder: 'e.g. cristiano' },
  { value: 'name', label: 'Full Name', placeholder: 'e.g. Cristiano Ronaldo' },
  { value: 'id', label: 'User ID', placeholder: 'e.g. 173560420' },
]

export function InstagramSearchForm({ onSuccess }: Props) {
  const [query, setQuery] = useState('')
  const [queryType, setQueryType] = useState<QueryType>('username')
  const mutation = useScanInstagramIntel()

  const selectedOption = QUERY_TYPE_OPTIONS.find((o) => o.value === queryType)!

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return
    mutation.mutate({ query: query.trim(), queryType }, { onSuccess })
  }, [query, queryType, mutation, onSuccess])

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Search By
        </label>
        <div className="flex flex-wrap gap-2">
          {QUERY_TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setQueryType(opt.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                queryType === opt.value
                  ? 'border-brand-500 bg-brand-900 text-brand-400'
                  : 'border-border-default text-text-secondary hover:border-brand-500 hover:text-brand-400'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label
          htmlFor="ig-intel-query"
          className="mb-2 block text-sm font-medium"
          style={{ color: 'var(--text-primary)' }}
        >
          {selectedOption.label}
        </label>
        <input
          id="ig-intel-query"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
          placeholder={selectedOption.placeholder}
          className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Searches public Instagram profiles. Only publicly visible data is collected.
        </p>
      </div>

      {mutation.error && (
        <div
          className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm"
          role="alert"
          style={{
            background: 'var(--danger-900)',
            borderColor: 'var(--danger-500)',
            color: 'var(--danger-500)',
          }}
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{mutation.error.message}</span>
        </div>
      )}

      <Button
        onClick={handleSubmit}
        disabled={!query.trim()}
        loading={mutation.isPending}
        className="w-full"
        size="lg"
        aria-label="Search Instagram profiles"
      >
        Search Instagram
      </Button>
    </div>
  )
}
