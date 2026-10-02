'use client';

/** Every job across engine and remote modules, the ones needing attention first. */
import { Play, Server, Workflow } from 'lucide-react';
import { Badge, EmptyState, Hint, RelativeTime } from '../data/data-ui';
import { moduleLabel, sortJobs } from './jobs-model';
import type { JobView, RunSummary } from './jobs-types';
import { Countdown, RunDuration, RunStatus, RunStrip } from './jobs-ui';

function Schedule({ job }: { job: JobView }) {
  if (!job.triggers.length) return <span className="data-muted">Manual only</span>;
  const [first, ...rest] = job.triggers;
  return (
    <span className="jobs-schedule">
      <span className="jobs-schedule-summary" title={first.spec}>
        {first.summary}
        {rest.length > 0 && <span className="data-muted"> +{rest.length}</span>}
      </span>
      {job.next_at && <Countdown iso={job.next_at} />}
    </span>
  );
}

function LastRun({ run }: { run: RunSummary | null }) {
  if (!run) return <span className="data-muted">Never ran</span>;
  return (
    <span className="jobs-last">
      <RunStatus status={run.status} />
      <span className="jobs-last-meta">
        <RelativeTime iso={run.started_at ?? run.fired_at} /> · <RunDuration run={run} />
      </span>
    </span>
  );
}

export function JobsTable({
  jobs,
  selected,
  onSelect,
  onRun,
  onOpenRun,
}: {
  jobs: JobView[];
  selected: string | null;
  onSelect: (job: JobView) => void;
  onRun: (job: JobView) => void;
  onOpenRun: (run: RunSummary) => void;
}) {
  if (!jobs.length) {
    return (
      <EmptyState icon={Workflow} title="No jobs yet">
        Modules declare jobs with JobDescriptor or the @job decorator; they show up here with their schedules and runs.
      </EmptyState>
    );
  }
  return (
    <div className="jobs-table" role="listbox" aria-label="Jobs">
      <div className="jobs-table-head" aria-hidden="true">
        <span>Job</span>
        <span>Schedule</span>
        <span>Recent runs</span>
        <span>Last run</span>
        <span className="data-align-end">Now</span>
        <span />
      </div>
      {sortJobs(jobs).map((job) => (
        <div
          key={job.key}
          role="option"
          aria-selected={selected === job.key}
          tabIndex={-1}
          data-job={job.key}
          className={`jobs-row${selected === job.key ? ' jobs-row-selected' : ''}`}
          onClick={() => onSelect(job)}
        >
          <span className="jobs-name">
            <span className="jobs-name-icon" aria-hidden="true">
              {job.location === 'remote' ? <Server size={15} /> : <Workflow size={15} />}
            </span>
            <span className="jobs-name-text">
              <span className="jobs-name-title">
                {job.name}
                {job.location === 'remote' && (
                  <Badge tone="info" title={`${job.instances} live instance(s)`}>
                    remote{job.instances > 1 ? ` ×${job.instances}` : ''}
                  </Badge>
                )}
              </span>
              <span className="jobs-name-module" title={job.module_id}>
                {moduleLabel(job.module_id)} <span className="data-muted">· {job.module_id}</span>
              </span>
            </span>
          </span>
          <Schedule job={job} />
          <RunStrip runs={job.recent} onOpen={onOpenRun} />
          <LastRun run={job.last_run} />
          <span className="jobs-now data-align-end">
            {job.running > 0 && <Badge tone="info">{job.running} running</Badge>}
            {(job.queued ?? 0) > 0 && <Badge tone="warn">{job.queued} queued</Badge>}
            {job.running === 0 && !job.queued && <span className="data-muted">idle</span>}
          </span>
          <span className="jobs-row-actions" onClick={(e) => e.stopPropagation()}>
            <Hint label={`Run ${job.name} now`}>
              <button type="button" className="data-button" onClick={() => onRun(job)} aria-label={`Run ${job.name} now`}>
                <Play size={13} aria-hidden="true" /> Run
              </button>
            </Hint>
          </span>
        </div>
      ))}
    </div>
  );
}
