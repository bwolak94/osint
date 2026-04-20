import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useScanCloudExposure } from '../hooks'
import type { CloudExposureScan } from '../types'

interface Props {
  onSuccess: (result: CloudExposureScan) => void
}

export function CloudScanForm({ onSuccess }: Props) {
  const [target, setTarget] = useState('')
  const scanMutation = useScanCloudExposure()

  const handleSubmit = useCallback(() => {
    if (!target.trim()) return
    scanMutation.mutate(target.trim(), { onSuccess })
  }, [target, scanMutation, onSuccess])

  const errorMessage = scanMutation.error?.message

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="cloud-target" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Domain or Organization Name
        </label>
        <input
          id="cloud-target"
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
          placeholder="example.com or Acme Corp"
          className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Searches GrayhatWarfare.com for publicly accessible S3, Azure Blob, and GCP Storage buckets
        </p>
      </div>

      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <Button onClick={handleSubmit} disabled={!target.trim()} loading={scanMutation.isPending} className="w-full" size="lg">
        Scan for Exposed Buckets
      </Button>
    </div>
  )
}
