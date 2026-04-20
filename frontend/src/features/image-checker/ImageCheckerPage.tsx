import { useState, useRef, useCallback } from 'react'
import { ScanSearch, History } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { ImageUpload } from './components/ImageUpload'
import { MetadataDisplay } from './components/MetadataDisplay'
import { HistoryTable } from './components/HistoryTable'
import type { ImageCheck } from './types'

export function ImageCheckerPage() {
  const [selectedCheck, setSelectedCheck] = useState<ImageCheck | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const scrollToResults = useCallback(() => {
    // Small delay to allow the DOM to render before scrolling
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }, [])

  const handleUploadSuccess = useCallback(
    (result: ImageCheck) => {
      setSelectedCheck(result)
      scrollToResults()
    },
    [scrollToResults],
  )

  const handleHistorySelect = useCallback(
    (check: ImageCheck) => {
      setSelectedCheck(check)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    [],
  )

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Image Metadata Analyzer
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Upload an image to extract EXIF metadata, GPS coordinates, and camera information
        </p>
      </div>

      {/* Upload section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ScanSearch className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Upload Image
            </h2>
          </div>
        </CardHeader>
        <CardBody>
          <ImageUpload onSuccess={handleUploadSuccess} />
        </CardBody>
      </Card>

      {/* Results section — only shown when a check is selected */}
      {selectedCheck !== null && (
        <div
          ref={resultsRef}
          className="animate-in fade-in slide-in-from-top-2 duration-300"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Results
              <span
                className="ml-2 font-normal"
                style={{ color: 'var(--text-tertiary)' }}
              >
                {selectedCheck.filename}
              </span>
            </h2>
            <button
              onClick={() => setSelectedCheck(null)}
              className="text-xs transition-colors hover:underline"
              style={{ color: 'var(--text-tertiary)' }}
              aria-label="Dismiss analysis results"
            >
              Dismiss
            </button>
          </div>
          <MetadataDisplay check={selectedCheck} />
        </div>
      )}

      {/* History section */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Analysis History
          </h2>
        </div>
        <HistoryTable onSelect={handleHistorySelect} />
      </div>
    </div>
  )
}
