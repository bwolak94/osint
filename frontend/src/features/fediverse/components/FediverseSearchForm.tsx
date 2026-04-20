import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useScanFediverse } from '../hooks'
import type { FediverseScan } from '../types'

interface Props {
  onSuccess: (result: FediverseScan) => void
}

export function FediverseSearchForm({ onSuccess }: Props) {
  const [query, setQuery] = useState('')
  const mutation = useScanFediverse()

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return
    mutation.mutate(query.trim(), { onSuccess })
  }, [query, mutation, onSuccess])

  return (
    <div className="space-y-4">
      <div>
        <label
          htmlFor="fediverse-query"
          className="mb-2 block text-sm font-medium"
          style={{ color: 'var(--text-primary)' }}
        >
          Username or Handle
        </label>
        <input
          id="fediverse-query"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit()
          }}
          placeholder="e.g. alice or alice@mastodon.social"
          className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Searches Bluesky (AT Protocol) and multiple Mastodon instances
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
        aria-label="Search Fediverse for username"
      >
        Search Fediverse
      </Button>
    </div>
  )
}
