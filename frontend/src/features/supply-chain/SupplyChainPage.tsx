import { useState, useRef, useCallback } from 'react'
import { Package, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { SupplyChainForm } from './components/SupplyChainForm'
import { SupplyChainResults } from './components/SupplyChainResults'
import { SupplyChainHistory } from './components/SupplyChainHistory'
import type { SupplyChainScan } from './types'

export function SupplyChainPage() {
  const [selectedScan, setSelectedScan] = useState<SupplyChainScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: SupplyChainScan) => {
    setSelectedScan(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Supply Chain Intelligence</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>Enumerate npm/PyPI packages for a GitHub user, org, or domain and check for CVEs via OSV.dev</p>
      </div>
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
          <SupplyChainResults scan={selectedScan} />
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
