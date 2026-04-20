import { useState, useRef, useCallback } from 'react'
import { Users, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { FediverseSearchForm } from './components/FediverseSearchForm'
import { FediverseResults } from './components/FediverseResults'
import { FediverseHistory } from './components/FediverseHistory'
import type { FediverseScan } from './types'

export function FediversePage() {
  const [currentScan, setCurrentScan] = useState<FediverseScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: FediverseScan) => {
    setCurrentScan(result)
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleHistorySelect = useCallback((scan: FediverseScan) => {
    setCurrentScan(scan)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Fediverse Scanner
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Search Bluesky (AT Protocol) and Mastodon for usernames — no API key required
        </p>
      </div>

      {/* Search card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Search Username
            </h2>
          </div>
        </CardHeader>
        <CardBody>
          <FediverseSearchForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {/* Results card — only shown when there is a current result */}
      {currentScan !== null && (
        <div
          ref={resultsRef}
          className="animate-in fade-in slide-in-from-top-2 duration-300"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results
              <span className="ml-2 font-normal" style={{ color: 'var(--text-tertiary)' }}>
                {currentScan.query}
              </span>
            </h2>
            <button
              onClick={() => setCurrentScan(null)}
              className="text-xs transition-colors hover:underline"
              style={{ color: 'var(--text-tertiary)' }}
              aria-label="Dismiss scan results"
            >
              Dismiss
            </button>
          </div>
          <FediverseResults scan={currentScan} />
        </div>
      )}

      {/* History card */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Scan History
          </h2>
        </div>
        <FediverseHistory onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
