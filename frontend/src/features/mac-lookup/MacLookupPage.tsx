import { useState, useRef, useCallback } from 'react'
import { Wifi, History, SearchX } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { MacInputForm } from './components/MacInputForm'
import { MacResultDisplay } from './components/MacResultDisplay'
import { MacHistoryTable } from './components/MacHistoryTable'
import type { MacLookup } from './types'

type LookupState = 'idle' | 'done'

export function MacLookupPage() {
  const [selectedLookup, setSelectedLookup] = useState<MacLookup | null>(null)
  const [lookupState, setLookupState] = useState<LookupState>('idle')
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: MacLookup) => {
    setSelectedLookup(result)
    setLookupState('done')
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((lookup: MacLookup) => {
    setSelectedLookup(lookup)
    setLookupState('done')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  // MAC lookup always returns a result object if the API succeeds — no-results means no manufacturer resolved
  const hasResults = selectedLookup !== null && selectedLookup.manufacturer !== null
  const lookupRanNoResults = lookupState === 'done' && selectedLookup !== null && selectedLookup.manufacturer === null

  return (
    <div className="space-y-6">
      <ToolHeader
        title="MAC Address Lookup"
        description={TOOL_INFO['mac-lookup'].short}
        details={TOOL_INFO['mac-lookup'].details}
      />

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

      {lookupState === 'idle' && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No lookup run yet"
        >
          <Wifi className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No lookup run yet — enter a MAC address above to begin
          </p>
        </div>
      )}

      {lookupRanNoResults && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border py-12 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          aria-label="No manufacturer found"
        >
          <SearchX className="mb-3 h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
          <p className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>
            No manufacturer found for this MAC address
          </p>
        </div>
      )}

      {(hasResults || (lookupState === 'done' && selectedLookup !== null && !lookupRanNoResults)) && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results
              <span className="ml-2 font-mono font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedLookup!.mac_address}</span>
            </h2>
            <button
              onClick={() => { setSelectedLookup(null); setLookupState('idle') }}
              className="text-xs transition-colors hover:underline"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Dismiss
            </button>
          </div>
          <MacResultDisplay lookup={selectedLookup!} />
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
