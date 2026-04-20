import { useState, useRef, useCallback } from 'react'
import { Globe, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { DomainInputForm } from './components/DomainInputForm'
import { PermutationResultsDisplay } from './components/PermutationResultsDisplay'
import { DomainScanHistory } from './components/DomainScanHistory'
import type { DomainPermutationScan } from './types'

export function DomainPermutationPage() {
  const [selectedScan, setSelectedScan] = useState<DomainPermutationScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: DomainPermutationScan) => {
    setSelectedScan(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((scan: DomainPermutationScan) => {
    setSelectedScan(scan)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

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

      {selectedScan !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Scan Results
              <span className="ml-2 font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedScan.target_domain}</span>
            </h2>
            <button onClick={() => setSelectedScan(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
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
