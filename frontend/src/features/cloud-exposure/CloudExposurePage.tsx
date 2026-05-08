import { useState, useRef, useCallback, lazy, Suspense } from 'react'
import { Cloud, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { CloudScanForm } from './components/CloudScanForm'
import { CloudScanHistory } from './components/CloudScanHistory'
import type { CloudExposureScan } from './types'

const CloudExposureResults = lazy(() =>
  import('./components/CloudExposureResults').then((m) => ({ default: m.CloudExposureResults })),
)

export function CloudExposurePage() {
  const [selectedScan, setSelectedScan] = useState<CloudExposureScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: CloudExposureScan) => {
    setSelectedScan(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((scan: CloudExposureScan) => {
    setSelectedScan(scan)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <ToolHeader
        title="Cloud Storage Exposure Scanner"
        description={TOOL_INFO['cloud-exposure'].short}
        details={TOOL_INFO['cloud-exposure'].details}
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cloud className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan Target</h2>
          </div>
        </CardHeader>
        <CardBody>
          <CloudScanForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {selectedScan !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results — <span className="font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedScan.target}</span>
            </h2>
            <button onClick={() => setSelectedScan(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <Suspense fallback={<div style={{ color: 'var(--text-tertiary)' }} className="py-4 text-sm">Loading results...</div>}>
            <CloudExposureResults scan={selectedScan} />
          </Suspense>
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scan History</h2>
        </div>
        <CloudScanHistory onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
