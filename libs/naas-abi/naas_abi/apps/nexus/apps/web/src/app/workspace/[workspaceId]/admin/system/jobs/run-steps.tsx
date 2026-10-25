'use client';

/** A workflow run's steps on one time axis: status, attempts, timing, errors, child runs. */
import { ArrowUpRight, ListOrdered, Waypoints } from 'lucide-react';
import { absoluteTime } from '../data/data-model';
import { Badge, EmptyState, Notice, useNow } from '../data/data-ui';
import { formatMs, isActive, stepBars } from './jobs-model';
import type { RunSummary, WorkflowDetail } from './jobs-types';
import { RunStatus } from './jobs-ui';

export function StepTimeline({
  run,
  workflow,
  onOpenChild,
}: {
  run: RunSummary;
  workflow: WorkflowDetail;
  /** Open a child run (its ``<module>/<run id>`` key). */
  onOpenChild: (key: string) => void;
}) {
  const live = isActive(run.status) || workflow.steps.some((s) => s.status === 'RUNNING');
  const now = useNow(live ? 1000 : 60_000);
  if (!workflow.steps.length) {
    return (
      <EmptyState icon={ListOrdered} title="No steps yet">
        {isActive(run.status)
          ? 'The workflow has not started a step. Each ctx.step and ctx.call shows up here as it starts.'
          : 'This run recorded no steps (its journal may have been removed with its retention).'}
      </EmptyState>
    );
  }
  return (
    <div className="steps">
      {workflow.truncated && (
        <Notice tone="warn">
          <span>Only the first {workflow.steps.length} steps are shown.</span>
        </Notice>
      )}
      <ol className="steps-list" aria-label="Steps">
        {stepBars(workflow.steps, now).map(({ step, offsetMs, durationMs, left, width }) => (
          <li key={step.key} className="step-row" data-step={step.key}>
            <div className="step-head">
              <RunStatus status={step.status} />
              <code className="step-key data-mono" title={step.key}>
                {step.key}
              </code>
              {step.kind === 'call' && (
                <Badge tone="info" title="Starts a run of a workflow">
                  call
                </Badge>
              )}
              {step.attempt > 1 && <Badge tone="warn">attempt {step.attempt}</Badge>}
              <span className="step-time data-num" title={step.started_at ? absoluteTime(step.started_at) : undefined}>
                {offsetMs === null ? '—' : `+${formatMs(offsetMs)}`} · {formatMs(durationMs)}
              </span>
            </div>
            <div className="step-bar" aria-hidden="true">
              <span className={`step-bar-fill step-bar-${step.status.toLowerCase()}`} style={{ left: `${left}%`, width: `${width}%` }} />
            </div>
            {step.child && (
              <button type="button" className="data-link step-child" onClick={() => step.child && onOpenChild(step.child.key)}>
                <Waypoints size={12} aria-hidden="true" /> {step.child.workflow}
                <span className="data-mono"> {step.child.run_id}</span>
                <ArrowUpRight size={12} aria-hidden="true" />
              </button>
            )}
            {step.error && <p className="step-error">{step.error}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
