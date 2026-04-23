import { useState, useRef, useCallback } from 'react'
import { Globe, History, SearchX } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { DomainInputForm } from './components/DomainInputForm'
import { PermutationResultsDisplay } from './components/PermutationResultsDisplay'
import { DomainScanHistory } from './components/DomainScanHistory'
import type { DomainPermutationScan } from './types'

type ScanState = 'idle' | 'done'

export function DomainPermutationPage() {
  const [selectedScan, setSelectedScan] = useState<DomainPermutationScan | null>(null)
  const [scanState, setScanState] = useState<ScanState>('idle')
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: DomainPermutationScan) => {
    setSelectedScan(result)
    setScanState('done')
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((scan: DomainPermutationScan) => {
    setSelectedScan(scan)
    setScanState('done')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const hasResults = selectedScan !== null && selectedScan.permutations.length > 0
  const scanRanNoResults = scanState === 'done' && selectedScan !== null && selectedScan.permutations.length === 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Domain Permutation Scanner</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Detect typosquatting and lookalike domains — generates permutations and resolves which ones are registered
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan Domain</h2>
          </div>
        </CardHeader>
        <CardBody>
          <DomainInputForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {scanState === 'idle' && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No scan run yet"
        >
          <Globe className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No scan run yet — enter a domain above to begin
          </p>
        </div>
      )}

      {scanRanNoResults && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No permutations found"
        >
          <SearchX className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No permutations found for this target
          </p>
        </div>
      )}

      {hasResults && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Scan Results
              <span className="ml-2 font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedScan.target_domain}</span>
            </h2>
            <button
              onClick={() => { setSelectedScan(null); setScanState('idle') }}
              className="text-xs transition-colors hover:underline"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Dismiss
            </button>
          </div>
          <PermutationResultsDisplay scan={selectedScan} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan History</h2>
        </div>
        <DomainScanHistory onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
