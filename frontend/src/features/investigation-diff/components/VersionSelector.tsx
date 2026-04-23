import { useState } from 'react';
import { GitBranch, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardBody } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { useInvestigationVersions } from '../hooks';
import type { InvestigationVersion } from '../types';

interface VersionSelectorProps {
  investigationId: string;
  onCompare: (versionA: string, versionB: string) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function VersionOption({ version }: { version: InvestigationVersion }) {
  return (
    <span className="flex flex-col gap-0.5">
      <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
        {version.label}
      </span>
      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        {formatDate(version.created_at)} &middot; {version.node_count} nodes &middot; {version.edge_count} edges
      </span>
    </span>
  );
}

export function VersionSelector({ investigationId, onCompare }: VersionSelectorProps) {
  const { data: versions, isLoading, isError } = useInvestigationVersions(investigationId);
  const [versionA, setVersionA] = useState('');
  const [versionB, setVersionB] = useState('');

  const canCompare =
    versionA.length > 0 && versionB.length > 0 && versionA !== versionB;

  const handleCompare = () => {
    if (canCompare) onCompare(versionA, versionB);
  };

  const selectClass =
    'w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors focus:border-brand-500';

  const renderSelect = (
    value: string,
    onChange: (v: string) => void,
    label: string,
    exclude: string,
  ) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={selectClass}
        style={{
          background: 'var(--bg-surface)',
          borderColor: 'var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
        disabled={isLoading || isError || !versions?.length}
      >
        <option value="">Select a version…</option>
        {versions?.map((v) => (
          <option key={v.version_id} value={v.version_id} disabled={v.version_id === exclude}>
            {v.label} — {formatDate(v.created_at)} ({v.node_count}N / {v.edge_count}E)
          </option>
        ))}
      </select>
    </div>
  );

  const selectedA = versions?.find((v) => v.version_id === versionA);
  const selectedB = versions?.find((v) => v.version_id === versionB);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Select Versions to Compare
          </h2>
          {isLoading && (
            <RefreshCw className="ml-auto h-3.5 w-3.5 animate-spin" style={{ color: 'var(--text-tertiary)' }} />
          )}
          {versions && (
            <Badge variant="neutral" size="sm" className="ml-auto">
              {versions.length} version{versions.length !== 1 ? 's' : ''}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardBody>
        {isError && (
          <p className="mb-4 text-sm" style={{ color: 'var(--danger-400)' }}>
            Failed to load versions. Verify the Investigation ID and try again.
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          {renderSelect(versionA, setVersionA, 'Version A (baseline)', versionB)}
          {renderSelect(versionB, setVersionB, 'Version B (comparison)', versionA)}
        </div>

        {selectedA && selectedB && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              { label: 'Version A', v: selectedA },
              { label: 'Version B', v: selectedB },
            ].map(({ label, v }) => (
              <div
                key={v.version_id}
                className="rounded-md border p-3"
                style={{ borderColor: 'var(--border-subtle)' }}
              >
                <p className="mb-1 text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
                  {label}
                </p>
                <VersionOption version={v} />
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={handleCompare}
            disabled={!canCompare}
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: 'var(--brand-500)',
              color: '#fff',
            }}
          >
            <GitBranch className="h-4 w-4" />
            Compare Versions
          </button>
        </div>
      </CardBody>
    </Card>
  );
}
