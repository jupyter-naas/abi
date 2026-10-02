'use client';

/** Runs, newest first: status, job, trigger, when, how long. */
import { ListChecks } from 'lucide-react';
import { absoluteTime } from '../data/data-model';
import { EmptyState, RelativeTime, SkeletonRows } from '../data/data-ui';
import { moduleLabel, startDelay, formatMs } from './jobs-model';
import type { RunSummary } from './jobs-types';
import { RunDuration, RunStatus, TriggerTag } from './jobs-ui';

export const STATUS_FILTERS: { id: string; label: string; statuses: string[] }[] = [
  { id: 'all', label: 'All', statuses: [] },
  { id: 'active', label: 'Running', statuses: ['RUNNING', 'RETRYING'] },
  { id: 'failed', label: 'Failed', statuses: ['FAILED', 'TIMED_OUT'] },
  { id: 'succeeded', label: 'Succeeded', statuses: ['SUCCEEDED'] },
  { id: 'cancelled', label: 'Cancelled', statuses: ['CANCELLED'] },
];

export function StatusFilter({ value, onChange }: { value: string[]; onChange: (statuses: string[]) => void }) {
  const active = STATUS_FILTERS.find((f) => f.statuses.join(',') === value.join(','))?.id ?? 'all';
  return (
    <div className="data-segmented" role="tablist" aria-label="Run status">
      {STATUS_FILTERS.map((f) => (
        <button
          key={f.id}
          type="button"
          role="tab"
          aria-selected={active === f.id}
          className={active === f.id ? 'data-segment data-segment-active' : 'data-segment'}
          onClick={() => onChange(f.statuses)}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}

export function RunsList({
  runs,
  selected,
  showJob,
  loading,
  onOpen,
}: {
  runs: RunSummary[] | null;
  selected: string | null;
  showJob: boolean;
  loading?: boolean;
  onOpen: (run: RunSummary) => void;
}) {
  if (runs === null) return <SkeletonRows rows={6} />;
  if (!runs.length) {
    return (
      <EmptyState icon={ListChecks} title={loading ? 'Loading runs…' : 'No runs match'}>
        Runs appear here as soon as a host picks up a trigger: a schedule tick, an event, or Run now.
      </EmptyState>
    );
  }
  return (
    <div className={`runs-list${showJob ? ' runs-list-with-job' : ''}`} role="listbox" aria-label="Runs">
      <div className="runs-head" aria-hidden="true">
        <span>Status</span>
        {showJob && <span>Job</span>}
        <span>Run</span>
        <span>Trigger</span>
        <span>Started</span>
        <span className="data-align-end">Duration</span>
        <span className="data-align-end">Attempt</span>
      </div>
      {runs.map((run) => {
        const delay = startDelay(run);
        return (
          <div
            key={run.key}
            role="option"
            aria-selected={selected === run.key}
            tabIndex={-1}
            data-run={run.key}
            className={`runs-row${selected === run.key ? ' runs-row-selected' : ''}`}
            onClick={() => onOpen(run)}
          >
            <span>
              <RunStatus status={run.status} />
            </span>
            {showJob && (
              <span className="runs-job">
                <span className="runs-job-name">{run.job}</span>
                <span className="data-muted" title={run.module_id}>
                  {moduleLabel(run.module_id)}
                </span>
              </span>
            )}
            <span className="data-mono runs-id" title={run.run_id}>
              {run.run_id}
            </span>
            <span>
              <TriggerTag kind={run.trigger.kind} />
            </span>
            <span className="runs-when" title={absoluteTime(run.started_at ?? run.fired_at)}>
              <RelativeTime iso={run.started_at ?? run.fired_at} />
              {delay !== null && delay >= 1000 && <span className="data-muted"> · waited {formatMs(delay)}</span>}
            </span>
            <span className="data-align-end">
              <RunDuration run={run} />
            </span>
            <span className={`data-align-end data-num${run.attempt > 1 ? ' runs-retried' : ''}`}>
              {run.attempt}/{run.max_attempts}
            </span>
          </div>
        );
      })}
    </div>
  );
}
