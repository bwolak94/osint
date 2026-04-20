import { useState } from 'react'
import { MapPin } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useRunImint } from './hooks'
import { ImintForm } from './components/ImintForm'
import { ImintResults } from './components/ImintResults'
import { ImintHistory } from './components/ImintHistory'
import type { ImintScan } from './types'

export function ImintPage() {
  const [activeScan, setActiveScan] = useState<ImintScan | null>(null)
  const { mutate: runScan, isPending } = useRunImint()

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
          <MapPin className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            IMINT / GEOINT
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Image forensics, geospatial intelligence, satellite analysis, sun chronolocation,
            ADS-B/AIS tracking, and deepfake detection
          </p>
        </div>
      </div>

      {/* Scan form */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">New Analysis</CardTitle>
          <CardDescription>
            Enter GPS coordinates (lat,lon) for geospatial modules, or an image URL for visual
            analysis. Modules are automatically selected based on input type.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ImintForm onSubmit={handleSubmit} isLoading={isPending} />
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
            {Array.from({ length: 6 }).map((_, i) => (
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
            <ImintResults scan={activeScan} />
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Analysis History</CardTitle>
          <CardDescription>Click a previous analysis to reload its results.</CardDescription>
        </CardHeader>
        <CardContent>
          <ImintHistory onSelect={setActiveScan} />
        </CardContent>
      </Card>
    </div>
  )
}
