import { CheckCircle2, Loader2, Clock, XCircle } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import type { ModuleProgress } from '../hooks'

interface ProgressPanelProps {
  progress: ModuleProgress[]
}

const STATUS_ICON: Record<ModuleProgress['status'], React.ReactNode> = {
  pending: <Clock className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />,
  running: <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'var(--brand-400)' }} />,
  done: <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--success-500)' }} />,
  error: <XCircle className="h-4 w-4" style={{ color: 'var(--danger-400)' }} />,
}

export function ProgressPanel({ progress }: ProgressPanelProps) {
  if (progress.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Running Modules
        </span>
      </CardHeader>
      <CardBody className="space-y-3">
        {progress.map((p) => (
          <div key={p.module} className="flex items-start gap-3">
            <div className="mt-0.5 shrink-0">{STATUS_ICON[p.status]}</div>
            <div className="min-w-0">
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {p.module}
              </p>
              {p.message && (
                <p className="text-xs truncate" style={{ color: 'var(--text-tertiary)' }}>
                  {p.message}
                </p>
              )}
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  )
}
