import { Brain, AlertTriangle, Lightbulb, ChevronRight } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { AiSynthesis } from '../types'

const riskVariant: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'neutral',
}

interface SynthesisPanelProps {
  synthesis: AiSynthesis
  targetLabel: string
  modulesRun: string[]
  totalFindings: number
}

export function SynthesisPanel({ synthesis, targetLabel, modulesRun, totalFindings }: SynthesisPanelProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              AI Synthesis
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={(riskVariant[synthesis.risk_level] ?? 'neutral') as 'danger' | 'warning' | 'info' | 'neutral'}>
              {synthesis.risk_level.toUpperCase()} RISK
            </Badge>
            <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>
              {Math.round(synthesis.confidence * 100)}% confidence
            </span>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-5">
        {/* Summary */}
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {synthesis.summary}
        </p>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Modules Run', value: modulesRun.length },
            { label: 'Total Findings', value: totalFindings },
            { label: 'Risk Level', value: synthesis.risk_level.charAt(0).toUpperCase() + synthesis.risk_level.slice(1) },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-lg border px-3 py-2 text-center"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}
            >
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
            </div>
          ))}
        </div>

        {/* Key findings */}
        {synthesis.key_findings.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>
              Key Findings
            </p>
            <ul className="space-y-2">
              {synthesis.key_findings.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                  <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" style={{ color: 'var(--warning-400)' }} />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommended pivots */}
        {synthesis.recommended_pivots.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>
              Recommended Next Steps
            </p>
            <ul className="space-y-1.5">
              {synthesis.recommended_pivots.map((p, i) => (
                <li key={i} className="flex items-center gap-2 text-sm" style={{ color: 'var(--brand-400)' }}>
                  <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                  {p}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Modules list */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>
            Modules Executed for <span style={{ color: 'var(--text-primary)' }}>{targetLabel}</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {modulesRun.map((m) => (
              <span
                key={m}
                className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs"
                style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
              >
                <Lightbulb className="h-3 w-3" style={{ color: 'var(--brand-400)' }} />
                {m}
              </span>
            ))}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
