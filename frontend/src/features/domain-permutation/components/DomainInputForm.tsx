import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useScanDomainPermutations } from '../hooks'
import type { DomainPermutationScan } from '../types'

interface Props {
  onSuccess: (result: DomainPermutationScan) => void
}

export function DomainInputForm({ onSuccess }: Props) {
  const [domain, setDomain] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const scanMutation = useScanDomainPermutations()

  const handleSubmit = useCallback(() => {
    setValidationError(null)
    const trimmed = domain.trim().toLowerCase()
    if (!trimmed) {
      setValidationError('Please enter a domain name')
      return
    }
    if (!trimmed.includes('.')) {
      setValidationError('Please enter a valid domain (e.g. example.com)')
      return
    }
    scanMutation.mutate(trimmed, { onSuccess })
  }, [domain, scanMutation, onSuccess])

  const errorMessage = scanMutation.error?.message ?? validationError

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="domain-input" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Target Domain
        </label>
        <input
          id="domain-input"
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
          placeholder="example.com"
          className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Generates typosquat permutations and resolves registered domains via DNS
        </p>
      </div>

      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <Button onClick={handleSubmit} disabled={!domain.trim()} loading={scanMutation.isPending} className="w-full" size="lg">
        {scanMutation.isPending ? 'Scanning (DNS resolution may take ~30s)...' : 'Scan for Lookalikes'}
      </Button>
    </div>
  )
}
