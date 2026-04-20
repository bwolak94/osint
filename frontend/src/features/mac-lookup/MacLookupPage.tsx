import { useState, useRef, useCallback } from 'react'
import { Wifi, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { MacInputForm } from './components/MacInputForm'
import { MacResultDisplay } from './components/MacResultDisplay'
import { MacHistoryTable } from './components/MacHistoryTable'
import type { MacLookup } from './types'

export function MacLookupPage() {
  const [selectedLookup, setSelectedLookup] = useState<MacLookup | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: MacLookup) => {
    setSelectedLookup(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((lookup: MacLookup) => {
    setSelectedLookup(lookup)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>MAC Address Lookup</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Identify the manufacturer, device type, and flags for any MAC address using the IEEE OUI registry
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Wifi className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>MAC Address Lookup</h2>
          </div>
        </CardHeader>
        <CardBody>
          <MacInputForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {selectedLookup !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results
              <span className="ml-2 font-mono font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedLookup.mac_address}</span>
            </h2>
            <button onClick={() => setSelectedLookup(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <MacResultDisplay lookup={selectedLookup} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Lookup History</h2>
        </div>
        <MacHistoryTable onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
