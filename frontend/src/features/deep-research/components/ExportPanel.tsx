import { useNavigate } from 'react-router-dom'
import { FileOutput, Download } from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import type { DeepResearchResult } from '../types'

interface ExportPanelProps {
  result: DeepResearchResult
}

/** Serialise key findings into a Markdown string for report pre-fill. */
function buildMarkdown(result: DeepResearchResult): string {
  const lines: string[] = [
    `# Deep Research Report: ${result.target_label}`,
    '',
    `**Risk Level:** ${result.ai_synthesis.risk_level.toUpperCase()}  `,
    `**Confidence:** ${Math.round(result.ai_synthesis.confidence * 100)}%  `,
    `**Total Findings:** ${result.total_findings}`,
    '',
    '## AI Summary',
    result.ai_synthesis.summary,
    '',
    '## Key Findings',
    ...result.ai_synthesis.key_findings.map((f) => `- ${f}`),
    '',
    '## Recommended Pivots',
    ...result.ai_synthesis.recommended_pivots.map((p) => `- ${p}`),
    '',
    '## Modules Run',
    ...result.modules_run.map((m) => `- ${m}`),
  ]

  if (result.socmint) {
    lines.push('', '## Social Media Profiles')
    result.socmint.social_profiles
      .filter((p) => p.found)
      .forEach((p) => lines.push(`- **${p.platform}**: ${p.url ?? 'found'}`))
  }

  if (result.email_intel && result.email_intel.breach_count > 0) {
    lines.push('', '## Breached Services')
    result.email_intel.breach_sources.forEach((b) => lines.push(`- ${b}`))
  }

  return lines.join('\n')
}

/** Download results as a JSON file. */
function downloadJson(result: DeepResearchResult) {
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `deep-research-${result.target_label.replace(/\s+/g, '-').toLowerCase()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export function ExportPanel({ result }: ExportPanelProps) {
  const navigate = useNavigate()

  const handleReportBuilder = () => {
    // Store pre-filled content in sessionStorage so ReportBuilderPage can read it
    const payload = {
      title: `Deep Research: ${result.target_label}`,
      markdown: buildMarkdown(result),
      source: 'deep-research',
      requestId: result.request_id,
    }
    sessionStorage.setItem('report_prefill', JSON.stringify(payload))
    navigate('/report-builder')
  }

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Export Results
            </p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Send to Report Builder or download raw JSON
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => downloadJson(result)}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors hover:opacity-80"
              style={{
                background: 'var(--bg-elevated)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-secondary)',
              }}
            >
              <Download className="h-4 w-4" />
              JSON
            </button>
            <button
              onClick={handleReportBuilder}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:opacity-90"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
            >
              <FileOutput className="h-4 w-4" />
              Open in Report Builder
            </button>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
