import { useState } from 'react'
import { FlaskConical, Users, Mail, Phone, Building2, Eye, X } from 'lucide-react'
import { ToolHeader } from '@/shared/components/ToolHeader'
import { TOOL_INFO } from '@/shared/lib/toolInfo'
import { useDeepResearch } from './hooks'
import { ResearchForm } from './components/ResearchForm'
import { SynthesisPanel } from './components/SynthesisPanel'
import { ProgressPanel } from './components/ProgressPanel'
import { SocmintTab } from './components/SocmintTab'
import { EmailTab } from './components/EmailTab'
import { PhoneTab } from './components/PhoneTab'
import { CorporateTab } from './components/CorporateTab'
import { DarkWebTab } from './components/DarkWebTab'
import { RelationsGraphPanel } from './components/RelationsGraphPanel'
import { ExportPanel } from './components/ExportPanel'
import type { DeepResearchResult } from './types'

const TABS = [
  { key: 'socmint', label: 'Social Media', icon: Users },
  { key: 'email_intel', label: 'Email Intel', icon: Mail },
  { key: 'phone_intel', label: 'Phone Intel', icon: Phone },
  { key: 'corporate', label: 'KRS / CEIDG', icon: Building2 },
  { key: 'dark_web', label: 'Dark Web', icon: Eye },
] as const

type TabKey = (typeof TABS)[number]['key']

export function DeepResearchPage() {
  const { run, cancel, isPending, result, progress, error } = useDeepResearch()
  const [activeTab, setActiveTab] = useState<TabKey>('socmint')

  const availableTabs = TABS.filter(({ key }) => result?.[key] != null)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: 'var(--bg-overlay)' }}
        >
          <FlaskConical className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
        </div>
        <ToolHeader
          title="Deep Research"
          description={TOOL_INFO['deep-research'].short}
          details={TOOL_INFO['deep-research'].details}
        />
      </div>

      {/* Input form */}
      <ResearchForm onSubmit={run} isLoading={isPending} />

      {/* Live progress during stream */}
      {isPending && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium animate-pulse" style={{ color: 'var(--brand-400)' }}>
              Research in progress…
            </p>
            <button
              onClick={cancel}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
          </div>
          <ProgressPanel progress={progress} />
        </div>
      )}

      {/* Error state */}
      {error && !isPending && (
        <div
          className="rounded-lg border px-4 py-3 text-sm"
          style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-700)', color: 'var(--danger-300)' }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {!isPending && result && (
        <ResultsView result={result} activeTab={activeTab} onTabChange={setActiveTab} availableTabs={availableTabs} />
      )}

      {/* Empty state */}
      {!isPending && !result && !error && (
        <div
          className="rounded-xl border py-20 text-center"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <FlaskConical className="mx-auto h-12 w-12 mb-3" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            Fill in any known identifiers above and run a deep research
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            Combines SOCMINT · Email intel (Holehe) · Phone lookup · KRS/CEIDG · Dark web monitoring
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Extracted to keep the main component lean
// ---------------------------------------------------------------------------

interface ResultsViewProps {
  result: DeepResearchResult
  activeTab: TabKey
  onTabChange: (tab: TabKey) => void
  availableTabs: typeof TABS[number][]
}

function ResultsView({ result, activeTab, onTabChange, availableTabs }: ResultsViewProps) {
  return (
    <div className="space-y-5">
      {/* Export row */}
      <ExportPanel result={result} />

      {/* AI Synthesis */}
      <SynthesisPanel
        synthesis={result.ai_synthesis}
        targetLabel={result.target_label}
        modulesRun={result.modules_run}
        totalFindings={result.total_findings}
      />

      {/* Relations graph */}
      <RelationsGraphPanel graph={result.relations_graph} />

      {/* Tabbed module results */}
      {availableTabs.length > 0 && (
        <div>
          {/* Tab bar */}
          <div
            className="flex gap-1 rounded-xl p-1 mb-4"
            style={{ background: 'var(--bg-elevated)' }}
          >
            {availableTabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => onTabChange(key)}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                style={
                  activeTab === key
                    ? { background: 'var(--bg-surface)', color: 'var(--text-primary)' }
                    : { color: 'var(--text-tertiary)' }
                }
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === 'socmint' && result.socmint && <SocmintTab data={result.socmint} />}
          {activeTab === 'email_intel' && result.email_intel && <EmailTab data={result.email_intel} />}
          {activeTab === 'phone_intel' && result.phone_intel && <PhoneTab data={result.phone_intel} />}
          {activeTab === 'corporate' && result.corporate && <CorporateTab data={result.corporate} />}
          {activeTab === 'dark_web' && result.dark_web && <DarkWebTab data={result.dark_web} />}
        </div>
      )}
    </div>
  )
}
