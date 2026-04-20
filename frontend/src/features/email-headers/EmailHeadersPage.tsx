import { useState, useRef, useCallback } from 'react'
import { Mail, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { HeaderInputForm } from './components/HeaderInputForm'
import { HeaderResultsDisplay } from './components/HeaderResultsDisplay'
import { HeaderHistoryTable } from './components/HeaderHistoryTable'
import type { EmailHeaderCheck } from './types'

export function EmailHeadersPage() {
  const [selectedCheck, setSelectedCheck] = useState<EmailHeaderCheck | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleSuccess = useCallback((result: EmailHeaderCheck) => {
    setSelectedCheck(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((check: EmailHeaderCheck) => {
    setSelectedCheck(check)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Email Header Analyzer</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Paste raw email headers to trace routing path, detect spoofing, and verify SPF/DKIM/DMARC authentication
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Paste Email Headers</h2>
          </div>
        </CardHeader>
        <CardBody>
          <HeaderInputForm onSuccess={handleSuccess} />
        </CardBody>
      </Card>

      {selectedCheck !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Results
              <span className="ml-2 font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedCheck.subject ?? '(no subject)'}</span>
            </h2>
            <button onClick={() => setSelectedCheck(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <HeaderResultsDisplay check={selectedCheck} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Analysis History</h2>
        </div>
        <HeaderHistoryTable onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
