import { Plus, Minus, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardBody } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { useInvestigationDiff } from '../hooks';
import type { DiffEntry, ChangeType } from '../types';

interface DiffResultsProps {
  investigationId: string;
  versionA: string;
  versionB: string;
}

const COLUMN_CONFIG: {
  key: ChangeType;
  label: string;
  icon: React.ReactNode;
  badgeVariant: 'success' | 'danger' | 'warning';
  accentVar: string;
  bgVar: string;
}[] = [
  {
    key: 'added',
    label: 'Added',
    icon: <Plus className="h-3.5 w-3.5" />,
    badgeVariant: 'success',
    accentVar: 'var(--success-500)',
    bgVar: 'rgba(34,197,94,0.06)',
  },
  {
    key: 'removed',
    label: 'Removed',
    icon: <Minus className="h-3.5 w-3.5" />,
    badgeVariant: 'danger',
    accentVar: 'var(--danger-400)',
    bgVar: 'rgba(248,113,113,0.06)',
  },
  {
    key: 'modified',
    label: 'Modified',
    icon: <RefreshCw className="h-3.5 w-3.5" />,
    badgeVariant: 'warning',
    accentVar: 'var(--warning-500)',
    bgVar: 'rgba(234,179,8,0.06)',
  },
];

function DiffEntryRow({
  entry,
  accentVar: _accentVar,
}: {
  entry: DiffEntry;
  accentVar: string;
}) {
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ borderColor: 'var(--border-subtle)' }}
    >
      <div className="flex items-start gap-2">
        <Badge variant="neutral" size="sm">
          {entry.entity_type}
        </Badge>
        <span
          className="min-w-0 break-all text-xs font-mono"
          style={{ color: 'var(--text-primary)' }}
        >
          {entry.value}
        </span>
      </div>

      {entry.change_type === 'modified' && (entry.old_value ?? entry.new_value) && (
        <div className="mt-2 space-y-1 pl-1">
          {entry.old_value !== undefined && (
            <p className="text-xs" style={{ color: 'var(--danger-400)' }}>
              <span className="mr-1 font-medium">Before:</span>
              <span className="font-mono">{entry.old_value}</span>
            </p>
          )}
          {entry.new_value !== undefined && (
            <p className="text-xs" style={{ color: 'var(--success-500)' }}>
              <span className="mr-1 font-medium">After:</span>
              <span className="font-mono">{entry.new_value}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DiffColumn({
  config,
  entries,
}: {
  config: (typeof COLUMN_CONFIG)[number];
  entries: DiffEntry[];
}) {
  return (
    <div className="flex flex-col">
      <div
        className="mb-3 flex items-center gap-2 rounded-md px-3 py-2"
        style={{ background: config.bgVar }}
      >
        <span style={{ color: config.accentVar }}>{config.icon}</span>
        <span className="text-xs font-semibold" style={{ color: config.accentVar }}>
          {config.label}
        </span>
        <Badge variant={config.badgeVariant} size="sm" className="ml-auto">
          {entries.length}
        </Badge>
      </div>

      {entries.length === 0 ? (
        <p className="px-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          No {config.label.toLowerCase()} entities.
        </p>
      ) : (
        <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
          {entries.map((entry, idx) => (
            <DiffEntryRow
              key={`${entry.entity_type}-${entry.value}-${idx}`}
              entry={entry}
              accentVar={config.accentVar}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function DiffResults({
  investigationId,
  versionA,
  versionB,
}: DiffResultsProps) {
  const { data, isLoading, isError } = useInvestigationDiff(
    investigationId,
    versionA,
    versionB,
  );

  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <div className="flex items-center gap-3 py-4">
            <RefreshCw
              className="h-4 w-4 animate-spin"
              style={{ color: 'var(--brand-500)' }}
            />
            <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
              Computing diff…
            </span>
          </div>
        </CardBody>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm" style={{ color: 'var(--danger-400)' }}>
            Failed to load diff. Please try again.
          </p>
        </CardBody>
      </Card>
    );
  }

  const totalChanges = data.added.length + data.removed.length + data.modified.length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Diff Results
          </h2>
          <Badge variant={totalChanges === 0 ? 'neutral' : 'brand'} size="sm">
            {totalChanges} change{totalChanges !== 1 ? 's' : ''}
          </Badge>

          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--success-500)' }}>
              +{data.added.length} added
            </span>
            <span className="text-xs" style={{ color: 'var(--danger-400)' }}>
              -{data.removed.length} removed
            </span>
            <span className="text-xs" style={{ color: 'var(--warning-500)' }}>
              ~{data.modified.length} modified
            </span>
          </div>
        </div>
      </CardHeader>
      <CardBody>
        {totalChanges === 0 ? (
          <p className="py-2 text-sm" style={{ color: 'var(--text-tertiary)' }}>
            The two versions are identical — no differences found.
          </p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-3">
            {COLUMN_CONFIG.map((col) => (
              <DiffColumn
                key={col.key}
                config={col}
                entries={data[col.key]}
              />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
