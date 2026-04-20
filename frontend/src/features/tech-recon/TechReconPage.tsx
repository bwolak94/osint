import { useState } from 'react'
import { ScanLine } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useRunTechRecon } from './hooks'
import { TechReconForm } from './components/TechReconForm'
import { TechReconResults } from './components/TechReconResults'
import { TechReconHistory } from './components/TechReconHistory'
import type { TechReconScan } from './types'

export function TechReconPage() {
  const [activeScan, setActiveScan] = useState<TechReconScan | null>(null)
  const { mutate: runScan, isPending } = useRunTechRecon()

  function handleSubmit(target: string, modules: string[]) {
    runScan({ target, modules }, { onSuccess: (scan) => setActiveScan(scan) })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: 'var(--bg-overlay)' }}
        >
          <ScanLine className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Infrastructure Recon
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Aggregate technical reconnaissance across DNS, ports, SSL, WAF, BGP, and more
          </p>
        </div>
      </div>

      {/* Scan form */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">New Scan</CardTitle>
          <CardDescription>Enter a domain or IP address and select which module groups to run.</CardDescription>
        </CardHeader>
        <CardContent>
          <TechReconForm onSubmit={handleSubmit} isLoading={isPending} />
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
                className="h-20 animate-pulse rounded-lg"
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
            <TechReconResults scan={activeScan} />
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
          <TechReconHistory onSelect={setActiveScan} />
        </CardContent>
      </Card>
    </div>
  )
}
