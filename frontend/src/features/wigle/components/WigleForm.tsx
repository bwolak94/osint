import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useSearchWigle } from '../hooks'
import type { WigleScan } from '../types'

interface Props {
  onSuccess: (result: WigleScan) => void
}

const PLACEHOLDERS: Record<string, string> = {
  bssid: 'AA:BB:CC:DD:EE:FF',
  ssid: 'NetworkName',
}

export function WigleForm({ onSuccess }: Props) {
  const [query, setQuery] = useState('')
  const [queryType, setQueryType] = useState('bssid')

  const mutation = useSearchWigle()

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return
    mutation.mutate(
      { query: query.trim(), queryType },
      { onSuccess },
    )
  }, [query, queryType, mutation, onSuccess])

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <div className="w-40 shrink-0">
          <label
            htmlFor="wigle-query-type"
            className="mb-2 block text-sm font-medium"
            style={{ color: 'var(--text-primary)' }}
          >
            Type
          </label>
          <select
            id="wigle-query-type"
            value={queryType}
            onChange={(e) => {
              setQueryType(e.target.value)
              setQuery('')
            }}
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)', background: 'var(--bg-surface)' }}
          >
            <option value="bssid" style={{ background: 'var(--bg-surface)' }}>
              BSSID / MAC
            </option>
            <option value="ssid" style={{ background: 'var(--bg-surface)' }}>
              Network Name
            </option>
          </select>
        </div>

        <div className="flex-1">
          <label
            htmlFor="wigle-query"
            className="mb-2 block text-sm font-medium"
            style={{ color: 'var(--text-primary)' }}
          >
            {queryType === 'bssid' ? 'BSSID (MAC Address)' : 'SSID (Network Name)'}
          </label>
          <input
            id="wigle-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit()
            }}
            placeholder={PLACEHOLDERS[queryType]}
            aria-label={queryType === 'bssid' ? 'Enter BSSID MAC address' : 'Enter SSID network name'}
            className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{
              borderColor: 'var(--border-default)',
              color: 'var(--text-primary)',
              background: 'var(--bg-surface)',
            }}
          />
        </div>
      </div>

      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Queries WiGLE.net (1B+ catalogued WiFi networks). Requires a valid{' '}
        <code className="font-mono">WIGLE_API_KEY</code> environment variable.
      </p>

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
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{mutation.error.message}</span>
        </div>
      )}

      <Button
        onClick={handleSubmit}
        disabled={!query.trim()}
        loading={mutation.isPending}
        className="w-full"
        size="lg"
        aria-label="Search WiGLE for the entered query"
      >
        Search WiGLE
      </Button>
    </div>
  )
}
