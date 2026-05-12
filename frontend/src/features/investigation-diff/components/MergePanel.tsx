import { useState } from 'react';
import { GitMerge, ChevronRight, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardBody, CardFooter } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { useMergeCandidates, useMergeInvestigations } from '../hooks';
import type { MergeStrategy } from '../types';

interface MergePanelProps {
  investigationId: string;
}

const STRATEGY_OPTIONS: {
  value: MergeStrategy;
  label: string;
  description: string;
}[] = [
  {
    value: 'union',
    label: 'Union',
    description:
      'Keep all entities from both investigations. Best when you want a comprehensive view with no data loss.',
  },
  {
    value: 'intersection',
    label: 'Intersection',
    description:
      'Keep only entities that appear in both investigations. Best for finding common ground between two branches.',
  },
];

function SimilarityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70
      ? 'var(--success-500)'
      : pct >= 40
      ? 'var(--warning-500)'
      : 'var(--danger-400)';

  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full"
        style={{ background: 'var(--border-subtle)' }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="w-9 text-right text-xs font-medium" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

export function MergePanel({ investigationId }: MergePanelProps) {
  const { data: candidates, isLoading, isError } = useMergeCandidates(investigationId);
  const { mutate: merge, isPending, isSuccess, data: mergeResult, reset } = useMergeInvestigations();

  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [strategy, setStrategy] = useState<MergeStrategy>('union');

  const canMerge =
    investigationId.trim().length > 0 &&
    selectedCandidateId.length > 0 &&
    !isPending;

  const handleMerge = () => {
    if (!canMerge) return;
    merge({
      source_id: investigationId,
      target_id: selectedCandidateId,
      strategy,
    });
  };

  if (isSuccess && mergeResult) {
    return (
      <Card>
        <CardBody>
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ background: 'rgba(34,197,94,0.12)' }}
            >
              <GitMerge className="h-6 w-6" style={{ color: 'var(--success-500)' }} />
            </div>
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Merge Complete
              </p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {mergeResult.merged_title}
              </p>
            </div>
            <div className="flex gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              <span>
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                  {mergeResult.node_count}
                </span>{' '}
                nodes
              </span>
              <span>
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                  {mergeResult.edge_count}
                </span>{' '}
                edges
              </span>
            </div>
            <a
              href={`/investigations/${mergeResult.merged_id}`}
              className="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
            >
              Open Merged Investigation
              <ChevronRight className="h-4 w-4" />
            </a>
            <button
              onClick={reset}
              className="text-xs underline-offset-2 hover:underline"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Merge another
            </button>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <GitMerge className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Merge Candidates
          </h2>
          {isLoading && (
            <RefreshCw
              className="ml-auto h-3.5 w-3.5 animate-spin"
              style={{ color: 'var(--text-tertiary)' }}
            />
          )}
        </div>
      </CardHeader>

      <CardBody className="space-y-5">
        {isError && (
          <p className="text-sm" style={{ color: 'var(--danger-400)' }}>
            Failed to load merge candidates. Verify the Investigation ID.
          </p>
        )}

        {!isLoading && !isError && candidates?.length === 0 && (
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            No merge candidates found for this investigation.
          </p>
        )}

        {candidates && candidates.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
              Select target investigation
            </p>
            {candidates.map((candidate) => {
              const isSelected = selectedCandidateId === candidate.id;
              return (
                <button
                  key={candidate.id}
                  onClick={() => setSelectedCandidateId(candidate.id)}
                  className="w-full rounded-md border px-4 py-3 text-left transition-all"
                  style={{
                    borderColor: isSelected ? 'var(--brand-500)' : 'var(--border-subtle)',
                    background: isSelected
                      ? 'rgba(99,102,241,0.06)'
                      : 'var(--bg-surface)',
                  }}
                >
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <span
                      className="text-sm font-medium"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {candidate.title}
                    </span>
                    <Badge variant="neutral" size="sm">
                      {candidate.shared_entity_count} shared
                    </Badge>
                  </div>
                  <SimilarityBar score={candidate.similarity_score} />
                  <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    Similarity score
                  </p>
                </button>
              );
            })}
          </div>
        )}

        <div className="space-y-2">
          <p className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
            Merge strategy
          </p>
          <div className="space-y-2">
            {STRATEGY_OPTIONS.map((opt) => {
              const isSelected = strategy === opt.value;
              return (
                <label
                  key={opt.value}
                  className="flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3 transition-all"
                  style={{
                    borderColor: isSelected
                      ? 'var(--brand-500)'
                      : 'var(--border-subtle)',
                    background: isSelected
                      ? 'rgba(99,102,241,0.06)'
                      : 'transparent',
                  }}
                >
                  <input
                    type="radio"
                    name="merge-strategy"
                    value={opt.value}
                    checked={isSelected}
                    onChange={() => setStrategy(opt.value)}
                    className="mt-0.5 accent-brand-500"
                  />
                  <div>
                    <p
                      className="text-sm font-medium"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {opt.label}
                    </p>
                    <p
                      className="mt-0.5 text-xs leading-relaxed"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {opt.description}
                    </p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      </CardBody>

      <CardFooter>
        <div className="flex items-center justify-between">
          {selectedCandidateId && (
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Strategy:{' '}
              <span style={{ color: 'var(--text-primary)' }}>
                {STRATEGY_OPTIONS.find((o) => o.value === strategy)?.label}
              </span>
            </p>
          )}
          <button
            onClick={handleMerge}
            disabled={!canMerge}
            className="ml-auto inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: 'var(--brand-500)', color: '#fff' }}
          >
            {isPending ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <GitMerge className="h-4 w-4" />
            )}
            {isPending ? 'Merging…' : 'Merge Investigations'}
          </button>
        </div>
      </CardFooter>
    </Card>
  );
}
