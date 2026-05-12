import { useState, useRef, useCallback, lazy, Suspense } from 'react'
import { Package, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { SupplyChainForm } from './components/SupplyChainForm'
import { SupplyChainHistory } from './components/SupplyChainHistory'
import type { SupplyChainScan } from './types'

const SupplyChainResults = lazy(() =>
  import('./components/SupplyChainResults').then((m) => ({ default: m.SupplyChainResults })),
)

export function SupplyChainPage() {
  const [selectedScan, setSelectedScan] = useState<SupplyChainScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: SupplyChainScan) => {
    setSelectedScan(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  return (
    <div className="space-y-6">
      <ToolHeader
        title="Supply Chain Intelligence"
        description={TOOL_INFO['supply-chain'].short}
        details={TOOL_INFO['supply-chain'].details}
      />
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan Target</h2>
          </div>
        </CardHeader>
        <CardBody><SupplyChainForm onSuccess={handleSuccess} /></CardBody>
      </Card>
      {selectedScan !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Results — <span className="font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedScan.target}</span></h2>
            <button onClick={() => setSelectedScan(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <Suspense fallback={<div style={{ color: 'var(--text-tertiary)' }} className="py-4 text-sm">Loading results...</div>}>
            <SupplyChainResults scan={selectedScan} />
          </Suspense>
        </div>
      )}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan History</h2>
        </div>
        <SupplyChainHistory onSelect={setSelectedScan} />
      </div>
    </div>
  )
}
