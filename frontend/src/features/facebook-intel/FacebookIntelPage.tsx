import { useState, useRef, useCallback } from 'react'
import { Facebook, History, SearchX } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { FacebookSearchForm } from './components/FacebookSearchForm'
import { FacebookResults } from './components/FacebookResults'
import { FacebookHistory } from './components/FacebookHistory'
import type { FacebookIntelScan } from './types'

type ScanState = 'idle' | 'done'

export function FacebookIntelPage() {
  const [currentScan, setCurrentScan] = useState<FacebookIntelScan | null>(null)
  const [scanState, setScanState] = useState<ScanState>('idle')
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: FacebookIntelScan) => {
    setCurrentScan(result)
    setScanState('done')
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleHistorySelect = useCallback((scan: FacebookIntelScan) => {
    setCurrentScan(scan)
    setScanState('done')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const hasResults = currentScan !== null && currentScan.results.length > 0
  const scanRanNoResults =
    scanState === 'done' && currentScan !== null && currentScan.results.length === 0

  return (
    <div className="space-y-6">
      <ToolHeader
        title="Facebook Intel"
        description={TOOL_INFO['facebook-intel'].short}
        details={TOOL_INFO['facebook-intel'].details}
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Facebook className="h-4 w-4" style={{ color: 'var(--brand-500)' }} aria-hidden="true" />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Profile Search
            </h2>
          </div>
        </CardHeader>
        <CardBody>
          <FacebookSearchForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {scanState === 'idle' && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No scan run yet"
        >
          <Facebook className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No scan run yet — enter a name, username, or ID above to begin
          </p>
        </div>
      )}

      {scanRanNoResults && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No profiles found"
        >
          <SearchX className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No public profiles found for this target
          </p>
        </div>
      )}

      {hasResults && (
        <div
          ref={resultsRef}
          className="animate-in fade-in slide-in-from-top-2 duration-300"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results
              <span className="ml-2 font-mono font-normal" style={{ color: 'var(--text-tertiary)' }}>
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
          <FacebookResults scan={currentScan} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Scan History
          </h2>
        </div>
        <FacebookHistory onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
