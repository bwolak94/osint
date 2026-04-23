import { useState, useCallback, useId } from 'react';
import { GitBranch, GitMerge } from 'lucide-react';
import { Card, CardHeader, CardBody } from '@/shared/components/Card';
import { VersionSelector } from './components/VersionSelector';
import { DiffResults } from './components/DiffResults';
import { MergePanel } from './components/MergePanel';

type Tab = 'diff' | 'merge';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  {
    id: 'diff',
    label: 'Diff Versions',
    icon: <GitBranch className="h-4 w-4" />,
  },
  {
    id: 'merge',
    label: 'Merge Investigations',
    icon: <GitMerge className="h-4 w-4" />,
  },
];

interface DiffState {
  versionA: string;
  versionB: string;
}

function InvestigationIdInput({
  value,
  onChange,
  inputId,
}: {
  value: string;
  onChange: (v: string) => void;
  inputId: string;
}) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Investigation
        </h2>
      </CardHeader>
      <CardBody>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor={inputId}
            className="text-xs font-medium"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Investigation ID
          </label>
          <input
            id={inputId}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="e.g. inv_01h8xg4j2k3m5n6p7q8r9s0t1"
            className="w-full rounded-md border px-3 py-2 text-sm font-mono outline-none transition-colors focus:border-brand-500 sm:max-w-md"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
          />
          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Enter the ID of the investigation you want to analyse.
          </p>
        </div>
      </CardBody>
    </Card>
  );
}

export function InvestigationDiffPage() {
  const [activeTab, setActiveTab] = useState<Tab>('diff');
  const [investigationId, setInvestigationId] = useState('');
  const [diffState, setDiffState] = useState<DiffState | null>(null);
  const inputId = useId();

  const handleTabChange = useCallback((tab: Tab) => {
    setActiveTab(tab);
    setDiffState(null);
  }, []);

  const handleInvestigationIdChange = useCallback((v: string) => {
    setInvestigationId(v);
    setDiffState(null);
  }, []);

  const handleCompare = useCallback((versionA: string, versionB: string) => {
    setDiffState({ versionA, versionB });
  }, []);

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1
          className="text-xl font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Investigation Diff &amp; Merge
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Compare historical versions of an investigation or merge two related
          investigations into one.
        </p>
      </div>

      {/* Tab bar */}
      <div
        className="flex gap-1 rounded-lg border p-1"
        style={{
          background: 'var(--bg-surface)',
          borderColor: 'var(--border-subtle)',
        }}
        role="tablist"
        aria-label="Investigation tools"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              id={`tab-${tab.id}`}
              onClick={() => handleTabChange(tab.id)}
              className="flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all"
              style={{
                background: isActive ? 'var(--brand-500)' : 'transparent',
                color: isActive ? '#fff' : 'var(--text-tertiary)',
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Investigation ID input — shared across tabs */}
      <InvestigationIdInput
        value={investigationId}
        onChange={handleInvestigationIdChange}
        inputId={inputId}
      />

      {/* Tab panels */}
      <div
        role="tabpanel"
        id="tabpanel-diff"
        aria-labelledby="tab-diff"
        hidden={activeTab !== 'diff'}
        className="space-y-4"
      >
        {investigationId.trim().length > 0 ? (
          <>
            <VersionSelector
              investigationId={investigationId}
              onCompare={handleCompare}
            />
            {diffState && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                <DiffResults
                  investigationId={investigationId}
                  versionA={diffState.versionA}
                  versionB={diffState.versionB}
                />
              </div>
            )}
          </>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            Enter an Investigation ID above to load its versions.
          </p>
        )}
      </div>

      <div
        role="tabpanel"
        id="tabpanel-merge"
        aria-labelledby="tab-merge"
        hidden={activeTab !== 'merge'}
        className="space-y-4"
      >
        {investigationId.trim().length > 0 ? (
          <MergePanel investigationId={investigationId} />
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            Enter an Investigation ID above to find merge candidates.
          </p>
        )}
      </div>
    </div>
  );
}
