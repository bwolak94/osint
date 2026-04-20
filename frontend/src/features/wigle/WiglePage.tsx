import { useState, useRef, useCallback } from 'react'
import { Wifi, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { WigleForm } from './components/WigleForm'
import { WigleResults } from './components/WigleResults'
import { WigleHistory } from './components/WigleHistory'
import type { WigleScan } from './types'

export function WiglePage() {
  const [currentScan, setCurrentScan] = useState<WigleScan | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: WigleScan) => {
    setCurrentScan(result)
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleHistorySelect = useCallback((scan: WigleScan) => {
    setCurrentScan(scan)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

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

      {/* Results — only shown when a scan is selected */}
      {currentScan !== null && (
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
              onClick={() => setCurrentScan(null)}
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
