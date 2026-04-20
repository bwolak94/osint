import { useRef, useState, useCallback, type DragEvent, type ChangeEvent } from 'react'
import { Upload, FileText, X, AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import { useUploadDoc } from '../hooks'
import type { DocMetadata } from '../types'

interface Props {
  onSuccess: (result: DocMetadata) => void
}

const ACCEPTED_EXTENSIONS = '.pdf,.docx,.xlsx,.pptx,.doc,.xls,.ppt,.odt'
const MAX_SIZE_BYTES = 50 * 1024 * 1024

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isAllowed(filename: string): boolean {
  const lower = filename.toLowerCase()
  return ['.pdf','.docx','.xlsx','.pptx','.doc','.xls','.ppt','.odt'].some((ext) => lower.endsWith(ext))
}

export function DocUpload({ onSuccess }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const uploadMutation = useUploadDoc()

  const validateAndSetFile = useCallback((file: File): boolean => {
    setValidationError(null)
    if (!isAllowed(file.name)) {
      setValidationError('Unsupported format. Accepted: PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, ODT')
      return false
    }
    if (file.size > MAX_SIZE_BYTES) {
      setValidationError(`File too large. Maximum is 50 MB (file is ${formatFileSize(file.size)})`)
      return false
    }
    setSelectedFile(file)
    return true
  }, [])

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) validateAndSetFile(file)
    e.target.value = ''
  }, [validateAndSetFile])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) validateAndSetFile(file)
  }, [validateAndSetFile])

  const handleClear = useCallback(() => {
    setSelectedFile(null)
    setValidationError(null)
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!selectedFile) return
    uploadMutation.mutate(selectedFile, {
      onSuccess: (result) => {
        onSuccess(result)
        handleClear()
      },
    })
  }, [selectedFile, uploadMutation, onSuccess, handleClear])

  const errorMessage = uploadMutation.error?.message ?? validationError

  return (
    <div className="space-y-4">
      {!selectedFile ? (
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload document drop zone"
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click() }}
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed px-8 py-16 text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
            isDragging ? 'border-brand-500 bg-brand-900/20' : 'border-border hover:border-brand-500/50 hover:bg-bg-overlay'
          }`}
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl" style={{ background: 'var(--bg-elevated)' }}>
            <Upload className="h-7 w-7" style={{ color: isDragging ? 'var(--brand-500)' : 'var(--text-tertiary)' }} />
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Drag &amp; drop a document, or click to browse</p>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, ODT — max 50 MB</p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-4 rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg" style={{ background: 'var(--bg-elevated)' }}>
            <FileText className="h-6 w-6" style={{ color: 'var(--brand-500)' }} />
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <p className="truncate text-sm font-medium" style={{ color: 'var(--text-primary)' }} title={selectedFile.name}>{selectedFile.name}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="neutral" size="sm">{formatFileSize(selectedFile.size)}</Badge>
            </div>
          </div>
          <button onClick={handleClear} aria-label="Remove selected file" className="shrink-0 rounded p-1 transition-colors hover:bg-bg-overlay">
            <X className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          </button>
        </div>
      )}
      <input ref={fileInputRef} type="file" accept={ACCEPTED_EXTENSIONS} onChange={handleFileChange} className="sr-only" aria-hidden="true" tabIndex={-1} />
      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
      <Button onClick={handleAnalyze} disabled={!selectedFile || !!validationError} loading={uploadMutation.isPending} className="w-full" size="lg">
        Extract Metadata
      </Button>
    </div>
  )
}
