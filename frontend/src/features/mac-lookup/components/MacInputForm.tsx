import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useMacLookup } from '../hooks'
import type { MacLookup } from '../types'

interface Props {
  onSuccess: (result: MacLookup) => void
}

const MAC_RE = /^([0-9A-Fa-f]{2}[:\-.]?){5}[0-9A-Fa-f]{2}$/

export function MacInputForm({ onSuccess }: Props) {
  const [mac, setMac] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const lookupMutation = useMacLookup()

  const handleSubmit = useCallback(() => {
    setValidationError(null)
    if (!mac.trim()) {
      setValidationError('Please enter a MAC address')
      return
    }
    if (!MAC_RE.test(mac.trim())) {
      setValidationError('Invalid MAC address format. Example: AA:BB:CC:DD:EE:FF')
      return
    }
    lookupMutation.mutate(mac.trim(), { onSuccess })
  }, [mac, lookupMutation, onSuccess])

  const errorMessage = lookupMutation.error?.message ?? validationError

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="mac-input" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          MAC Address
        </label>
        <input
          id="mac-input"
          type="text"
          value={mac}
          onChange={(e) => setMac(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
          placeholder="AA:BB:CC:DD:EE:FF"
          className="w-full rounded-lg border bg-transparent px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          aria-label="MAC address input"
        />
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Supported formats: AA:BB:CC:DD:EE:FF · AA-BB-CC-DD-EE-FF · AABBCCDDEEFF
        </p>
      </div>

      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <Button onClick={handleSubmit} disabled={!mac.trim()} loading={lookupMutation.isPending} className="w-full" size="lg">
        Lookup MAC Address
      </Button>
    </div>
  )
}
