import { useState, useRef, useCallback } from 'react'
import { Bug, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { StealerQueryForm } from './components/StealerQueryForm'
import { StealerResultsDisplay } from './components/StealerResultsDisplay'
import { StealerHistoryTable } from './components/StealerHistoryTable'
import type { StealerLogCheck } from './types'

export function StealerLogsPage() {
  const [selectedCheck, setSelectedCheck] = useState<StealerLogCheck | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: StealerLogCheck) => {
    setSelectedCheck(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((check: StealerLogCheck) => {
    setSelectedCheck(check)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Stealer Log Intelligence</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Check if an email, domain, or IP appears in infostealer logs — LummaC2, RedLine, Vidar, and more
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bug className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Query Stealer Logs</h2>
          </div>
        </CardHeader>
        <CardBody>
          <StealerQueryForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {selectedCheck !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Results — <span className="font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedCheck.query}</span>
            </h2>
            <button onClick={() => setSelectedCheck(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <StealerResultsDisplay check={selectedCheck} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Query History</h2>
        </div>
        <StealerHistoryTable onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
