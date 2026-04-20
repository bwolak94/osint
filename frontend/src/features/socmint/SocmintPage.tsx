import { useState } from 'react'
import { Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useRunSocmint } from './hooks'
import { SocmintForm } from './components/SocmintForm'
import { SocmintResults } from './components/SocmintResults'
import { SocmintHistory } from './components/SocmintHistory'
import type { SocmintScan } from './types'

export function SocmintPage() {
  const [activeScan, setActiveScan] = useState<SocmintScan | null>(null)
  const { mutate: runScan, isPending } = useRunSocmint()

  function handleSubmit(target: string, targetType: string, modules: string[]) {
    runScan(
      { target, target_type: targetType as SocmintScan['target_type'], modules },
      { onSuccess: (scan) => setActiveScan(scan) }
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: 'var(--bg-overlay)' }}
        >
          <Users className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            SOCMINT Analysis
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Social Media Intelligence — Modules 21-40. Profile analysis, behavioral patterns, and
            identity correlation.
          </p>
        </div>
      </div>

      {/* Scan form */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">New SOCMINT Scan</CardTitle>
          <CardDescription>
            Enter a target identifier and select which intelligence modules to run. Username targets
            are most comprehensive.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SocmintForm onSubmit={handleSubmit} isLoading={isPending} />
        </CardContent>
      </Card>

      {/* Loading skeleton */}
      {isPending && (
        <div className="space-y-3">
          <div
            className="h-6 w-48 animate-pulse rounded"
            style={{ background: 'var(--bg-overlay)' }}
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-lg"
                style={{ background: 'var(--bg-overlay)' }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {!isPending && activeScan && (
        <Card>
          <CardContent className="pt-5">
            <SocmintResults scan={activeScan} />
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Scan History</CardTitle>
          <CardDescription>Click a previous scan to reload its results.</CardDescription>
        </CardHeader>
        <CardContent>
          <SocmintHistory onSelect={setActiveScan} />
        </CardContent>
      </Card>
    </div>
  )
}
