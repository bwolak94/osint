import { useState, useRef, useCallback } from 'react'
import { Users, History, SearchX } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { FediverseSearchForm } from './components/FediverseSearchForm'
import { FediverseResults } from './components/FediverseResults'
import { FediverseHistory } from './components/FediverseHistory'
import type { FediverseScan } from './types'

type ScanState = 'idle' | 'done'

export function FediversePage() {
  const [currentScan, setCurrentScan] = useState<FediverseScan | null>(null)
  const [scanState, setScanState] = useState<ScanState>('idle')
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: FediverseScan) => {
    setCurrentScan(result)
    setScanState('done')
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleHistorySelect = useCallback((scan: FediverseScan) => {
    setCurrentScan(scan)
    setScanState('done')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const hasResults = currentScan !== null && currentScan.results.length > 0
  const scanRanNoResults = scanState === 'done' && currentScan !== null && currentScan.results.length === 0

  return (
    <div className="space-y-6">
      <ToolHeader
        title="Fediverse Scanner"
        description={TOOL_INFO['fediverse'].short}
        details={TOOL_INFO['fediverse'].details}
      />

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

      {/* Before scan: idle empty state */}
      {scanState === 'idle' && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No scan run yet"
        >
          <Users className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No scan run yet — enter a username above to begin
          </p>
        </div>
      )}

      {/* After scan, no results */}
      {scanRanNoResults && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No profiles found"
        >
          <SearchX className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No profiles found for this target
          </p>
        </div>
      )}

      {/* Results card — only shown when there are results */}
      {hasResults && (
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
              onClick={() => { setCurrentScan(null); setScanState('idle') }}
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
