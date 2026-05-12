import { useState, useCallback, useId } from 'react'
import { FileText, Plus, Trash2, Download, AlertCircle, Eye, Edit3 } from 'lucide-react'
import { Card, CardHeader, CardBody, CardFooter } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { Button } from '@/shared/components/Button'
import { LoadingSpinner } from '@/shared/components/LoadingSpinner'
import { useGenerateOSCPReport } from '../hooks'
import type { ReportFinding, OSCPReportResult } from '../types'

type SeverityVariant = 'danger' | 'warning' | 'info' | 'neutral'

const severityVariant: Record<ReportFinding['severity'], SeverityVariant> = {
  Critical: 'danger',
  High: 'danger',
  Medium: 'warning',
  Low: 'info',
}

function createBlankFinding(id: string): ReportFinding {
  return {
    id,
    title: '',
    severity: 'Medium',
    description: '',
    proofOfConcept: '',
    remediation: '',
    cveIds: [],
  }
}

interface FindingEditorProps {
  finding: ReportFinding
  index: number
  onChange: (id: string, patch: Partial<ReportFinding>) => void
  onRemove: (id: string) => void
}

function FindingEditor({ finding, index, onChange, onRemove }: FindingEditorProps) {
  const headingId = useId()
  return (
    <article
      aria-labelledby={headingId}
      className="rounded-lg border p-4 space-y-3"
      style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 id={headingId} className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
          Finding #{index + 1}
        </h3>
        <button
          type="button"
          onClick={() => onRemove(finding.id)}
          className="rounded p-1 transition-opacity hover:opacity-70"
          style={{ color: 'var(--danger-500)' }}
          aria-label={`Remove finding #${index + 1}`}
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Title *
          </label>
          <input
            type="text"
            value={finding.title}
            onChange={(e) => onChange(finding.id, { title: e.target.value })}
            placeholder="SQL Injection in /api/login"
            className="w-full rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
            aria-required="true"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            Severity
          </label>
          <select
            value={finding.severity}
            onChange={(e) => onChange(finding.id, { severity: e.target.value as ReportFinding['severity'] })}
            className="w-full rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)', background: 'var(--bg-surface)' }}
            aria-label="Severity level"
          >
            {(['Critical', 'High', 'Medium', 'Low'] as const).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Description *
        </label>
        <textarea
          value={finding.description}
          onChange={(e) => onChange(finding.id, { description: e.target.value })}
          placeholder="Describe the vulnerability..."
          rows={2}
          className="w-full resize-y rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          aria-required="true"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Proof of Concept
        </label>
        <textarea
          value={finding.proofOfConcept}
          onChange={(e) => onChange(finding.id, { proofOfConcept: e.target.value })}
          placeholder="curl -X POST ... or steps to reproduce..."
          rows={2}
          className="w-full resize-y rounded-md border bg-transparent px-2.5 py-1.5 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Remediation
        </label>
        <textarea
          value={finding.remediation}
          onChange={(e) => onChange(finding.id, { remediation: e.target.value })}
          placeholder="Patch, configuration change, or mitigation steps..."
          rows={2}
          className="w-full resize-y rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            CVSS Score (0–10)
          </label>
          <input
            type="number"
            min={0}
            max={10}
            step={0.1}
            value={finding.cvssScore ?? ''}
            onChange={(e) => onChange(finding.id, e.target.value ? { cvssScore: Number(e.target.value) } : {})}
            placeholder="7.5"
            className="w-full rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            CVE IDs (comma-separated)
          </label>
          <input
            type="text"
            value={finding.cveIds?.join(', ') ?? ''}
            onChange={(e) =>
              onChange(finding.id, {
                cveIds: e.target.value.split(',').map((c) => c.trim()).filter(Boolean),
              })
            }
            placeholder="CVE-2023-1234, CVE-2024-5678"
            className="w-full rounded-md border bg-transparent px-2.5 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
          />
        </div>
      </div>
    </article>
  )
}

function MarkdownPreview({ report }: { report: OSCPReportResult }) {
  const handleDownload = useCallback(() => {
    const blob = new Blob([report.reportMarkdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `oscp-report-${report.investigationId}.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [report])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Generated Report Preview
        </h3>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleDownload}
          leftIcon={<Download className="h-3.5 w-3.5" aria-hidden="true" />}
        >
          Export Markdown
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {report.findings.map((f) => (
          <div key={f.id} className="flex items-center gap-1.5">
            <Badge variant={severityVariant[f.severity]} size="sm">{f.severity}</Badge>
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{f.title}</span>
          </div>
        ))}
      </div>

      <pre
        className="overflow-x-auto overflow-y-auto rounded-lg p-4 text-xs leading-relaxed"
        style={{
          background: 'var(--bg-overlay)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-subtle)',
          maxHeight: '400px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
        aria-label="Report markdown preview"
      >
        {report.reportMarkdown}
      </pre>
    </div>
  )
}

export function OSCPReportPanel() {
  const [investigationId, setInvestigationId] = useState('')
  const [findings, setFindings] = useState<ReportFinding[]>([createBlankFinding(crypto.randomUUID())])
  const [result, setResult] = useState<OSCPReportResult | null>(null)
  const [previewMode, setPreviewMode] = useState(false)

  const mutation = useGenerateOSCPReport()

  const addFinding = useCallback(() => {
    setFindings((prev) => [...prev, createBlankFinding(crypto.randomUUID())])
  }, [])

  const removeFinding = useCallback((id: string) => {
    setFindings((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const updateFinding = useCallback((id: string, patch: Partial<ReportFinding>) => {
    setFindings((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)))
  }, [])

  const handleGenerate = useCallback(() => {
    const validFindings = findings.filter((f) => f.title.trim() && f.description.trim())
    if (validFindings.length === 0) return
    mutation.mutate(
      { investigationId: investigationId.trim() || 'manual', findings: validFindings },
      { onSuccess: (r: OSCPReportResult) => { setResult(r); setPreviewMode(true) } },
    )
  }, [investigationId, findings, mutation])

  const validCount = findings.filter((f) => f.title.trim() && f.description.trim()).length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>OSCP-Style Report Generator</h2>
          </div>
          {result && (
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => setPreviewMode(false)}
                className={`flex items-center gap-1 rounded px-2.5 py-1 text-xs transition-all ${!previewMode ? 'font-semibold' : 'opacity-50 hover:opacity-80'}`}
                style={{ color: 'var(--text-primary)', background: !previewMode ? 'var(--bg-overlay)' : 'transparent' }}
                aria-pressed={!previewMode}
              >
                <Edit3 className="h-3 w-3" aria-hidden="true" />
                Edit
              </button>
              <button
                type="button"
                onClick={() => setPreviewMode(true)}
                className={`flex items-center gap-1 rounded px-2.5 py-1 text-xs transition-all ${previewMode ? 'font-semibold' : 'opacity-50 hover:opacity-80'}`}
                style={{ color: 'var(--text-primary)', background: previewMode ? 'var(--bg-overlay)' : 'transparent' }}
                aria-pressed={previewMode}
              >
                <Eye className="h-3 w-3" aria-hidden="true" />
                Preview
              </button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardBody className="space-y-4">
        {previewMode && result ? (
          <MarkdownPreview report={result} />
        ) : (
          <>
            <div>
              <label htmlFor="investigation-id" className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Investigation ID (optional)
              </label>
              <input
                id="investigation-id"
                type="text"
                value={investigationId}
                onChange={(e) => setInvestigationId(e.target.value)}
                placeholder="inv-12345 or leave blank"
                className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                  Findings ({findings.length})
                </h3>
                <Badge variant="neutral" size="sm">{validCount} ready</Badge>
              </div>
              {findings.map((f, i) => (
                <FindingEditor
                  key={f.id}
                  finding={f}
                  index={i}
                  onChange={updateFinding}
                  onRemove={removeFinding}
                />
              ))}
              <Button
                variant="ghost"
                size="sm"
                onClick={addFinding}
                leftIcon={<Plus className="h-3.5 w-3.5" aria-hidden="true" />}
              >
                Add Finding
              </Button>
            </div>

            {mutation.error && (
              <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{mutation.error.message}</span>
              </div>
            )}
          </>
        )}
      </CardBody>

      {!previewMode && (
        <CardFooter>
          <Button
            onClick={handleGenerate}
            disabled={validCount === 0}
            loading={mutation.isPending}
            className="w-full"
          >
            {mutation.isPending && <LoadingSpinner size="sm" className="mr-2" />}
            Generate OSCP Report
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
