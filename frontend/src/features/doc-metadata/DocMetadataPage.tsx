import { useState, useRef, useCallback } from 'react'
import { FileSearch, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { DocUpload } from './components/DocUpload'
import { DocMetadataDisplay } from './components/DocMetadataDisplay'
import { DocHistoryTable } from './components/DocHistoryTable'
import type { DocMetadata } from './types'

export function DocMetadataPage() {
  const [selectedDoc, setSelectedDoc] = useState<DocMetadata | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const handleUploadSuccess = useCallback((result: DocMetadata) => {
    setSelectedDoc(result)
    setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [])

  const handleHistorySelect = useCallback((doc: DocMetadata) => {
    setSelectedDoc(doc)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      <ToolHeader
        title="Document Metadata Extractor"
        description={TOOL_INFO['doc-metadata'].short}
        details={TOOL_INFO['doc-metadata'].details}
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Upload Document</h2>
          </div>
        </CardHeader>
        <CardBody>
          <DocUpload onSuccess={handleUploadSuccess} />
        </CardBody>
      </Card>

      {selectedDoc !== null && (
        <div ref={resultsRef} className="animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Results
              <span className="ml-2 font-normal" style={{ color: 'var(--text-tertiary)' }}>{selectedDoc.filename}</span>
            </h2>
            <button onClick={() => setSelectedDoc(null)} className="text-xs transition-colors hover:underline" style={{ color: 'var(--text-tertiary)' }}>Dismiss</button>
          </div>
          <DocMetadataDisplay doc={selectedDoc} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Analysis History</h2>
        </div>
        <DocHistoryTable onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
