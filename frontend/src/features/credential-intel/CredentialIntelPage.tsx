import { useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useRunCredentialIntel } from './hooks'
import { CredentialIntelForm } from './components/CredentialIntelForm'
import { CredentialIntelResults } from './components/CredentialIntelResults'
import { CredentialIntelHistory } from './components/CredentialIntelHistory'
import type { CredentialIntelScan } from './types'

export function CredentialIntelPage() {
  const [activeScan, setActiveScan] = useState<CredentialIntelScan | null>(null)
  const { mutate: runScan, isPending } = useRunCredentialIntel()

  function handleSubmit(
    target: string,
    targetType: CredentialIntelScan['target_type'],
    modules: string[],
  ) {
    runScan({ target, target_type: targetType, modules }, { onSuccess: (scan) => setActiveScan(scan) })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: 'var(--bg-overlay)' }}
        >
          <ShieldAlert className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Credential Intelligence
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Domain III - Modules 41-60. Breach aggregation, hash analysis, exposure detection, and threat correlation.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">New Scan</CardTitle>
          <CardDescription>
            Analyze emails for breaches, domains for exposed configs, IPs for compromise, or hash strings for algorithm identification.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CredentialIntelForm onSubmit={handleSubmit} isLoading={isPending} />
        </CardContent>
      </Card>

      {isPending && (
        <div className="space-y-3">
          <div className="h-6 w-48 animate-pulse rounded" style={{ background: 'var(--bg-overlay)' }} />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-lg" style={{ background: 'var(--bg-overlay)' }} />
            ))}
          </div>
        </div>
      )}

      {!isPending && activeScan && (
        <Card>
          <CardContent className="pt-5">
            <CredentialIntelResults scan={activeScan} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Scan History</CardTitle>
          <CardDescription>Click any previous scan to reload its results.</CardDescription>
        </CardHeader>
        <CardContent>
          <CredentialIntelHistory onSelect={setActiveScan} />
        </CardContent>
      </Card>
    </div>
  )
}
