import { useState, useRef, useCallback } from 'react'
import { Wifi, History, SearchX } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { WigleForm } from './components/WigleForm'
import { WigleResults } from './components/WigleResults'
import { WigleHistory } from './components/WigleHistory'
import type { WigleScan } from './types'

type ScanState = 'idle' | 'done'

export function WiglePage() {
  const [currentScan, setCurrentScan] = useState<WigleScan | null>(null)
  const [scanState, setScanState] = useState<ScanState>('idle')
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: WigleScan) => {
    setCurrentScan(result)
    setScanState('done')
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleHistorySelect = useCallback((scan: WigleScan) => {
    setCurrentScan(scan)
    setScanState('done')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const hasResults = currentScan !== null && currentScan.results.length > 0
  const scanRanNoResults = scanState === 'done' && currentScan !== null && currentScan.results.length === 0

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          WiGLE WiFi Geolocation
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Look up a BSSID or SSID on WiGLE.net to retrieve historical physical location data for
          WiFi networks
        </p>
      </div>

      {/* Search form */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Wifi className="h-4 w-4" style={{ color: 'var(--brand-500)' }} aria-hidden="true" />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              WiGLE Search
            </h2>
          </div>
        </CardHeader>
        <CardBody>
          <WigleForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {/* Before scan: idle empty state */}
      {scanState === 'idle' && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No scan run yet"
        >
          <Wifi className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No scan run yet — enter a BSSID or SSID above to begin
          </p>
        </div>
      )}

      {/* After scan, no results */}
      {scanRanNoResults && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No networks found"
        >
          <SearchX className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No networks found for this target
          </p>
        </div>
      )}

      {/* Results — only shown when a scan has results */}
      {hasResults && (
        <div
          ref={resultsRef}
          className="animate-in fade-in slide-in-from-top-2 duration-300"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results{' '}
              <span className="font-mono font-normal" style={{ color: 'var(--text-tertiary)' }}>
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
          <WigleResults scan={currentScan} />
        </div>
      )}

      {/* History */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <History
            className="h-4 w-4"
            style={{ color: 'var(--text-tertiary)' }}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Scan History
          </h2>
        </div>
        <WigleHistory onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
