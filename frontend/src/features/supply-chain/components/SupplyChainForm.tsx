import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useScanSupplyChain } from '../hooks'
import type { SupplyChainScan } from '../types'

interface Props {
  onSuccess: (result: SupplyChainScan) => void
}

const TARGET_TYPES = [
  { value: 'github_user', label: 'GitHub User' },
  { value: 'github_org', label: 'GitHub Org' },
  { value: 'domain', label: 'Domain' },
]

export function SupplyChainForm({ onSuccess }: Props) {
  const [target, setTarget] = useState('')
  const [targetType, setTargetType] = useState('github_user')
  const mutation = useScanSupplyChain()

  const handleSubmit = useCallback(() => {
    if (!target.trim()) return
    mutation.mutate({ target: target.trim(), targetType }, { onSuccess })
  }, [target, targetType, mutation, onSuccess])

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <div className="w-40 shrink-0">
          <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Target Type</label>
          <select value={targetType} onChange={(e) => setTargetType(e.target.value)} className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500" style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}>
            {TARGET_TYPES.map((t) => <option key={t.value} value={t.value} style={{ background: 'var(--bg-surface)' }}>{t.label}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Target</label>
          <input type="text" value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }} placeholder={targetType === 'domain' ? 'example.com' : 'username-or-org'} className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500" style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }} />
        </div>
      </div>
      {mutation.error && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{mutation.error.message}</span>
        </div>
      )}
      <Button onClick={handleSubmit} disabled={!target.trim()} loading={mutation.isPending} className="w-full" size="lg">Scan Packages</Button>
    </div>
  )
}
