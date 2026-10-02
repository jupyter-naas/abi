'use client';

/** One job: its schedule and next ticks, health, queue, settings, and its runs. */
import { AlertTriangle, Clock, Hand, Play, Radio, type LucideIcon } from 'lucide-react';
import { Badge, Notice, RelativeTime } from '../data/data-ui';
import { FAILED, formatMs, health, statusLabel } from './jobs-model';
import type { JobView, RunSummary } from './jobs-types';
import { Countdown, RunStrip } from './jobs-ui';
import { RunsList, StatusFilter } from './runs-list';

const KIND_ICONS: Record<string, LucideIcon> = { cron: Clock, every: Clock, event: Radio };

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="job-card">
      <h3 className="job-card-title">{title}</h3>
      {children}
    </section>
  );
}

export function JobDetail({
  job,
  runs,
  statuses,
  selectedRun,
  onStatuses,
  onOpenRun,
  onRun,
}: {
  job: JobView;
  runs: RunSummary[] | null;
  statuses: string[];
  selectedRun: string | null;
  onStatuses: (statuses: string[]) => void;
  onOpenRun: (run: RunSummary) => void;
  onRun: () => void;
}) {
  const h = health(job.recent);
  return (
    <div className="job-detail">
      <header className="job-detail-header">
        <div className="job-detail-heading">
          <div className="job-detail-title-row">
            <h2 className="job-detail-title">{job.name}</h2>
            <Badge tone={job.location === 'remote' ? 'info' : 'neutral'}>
              {job.location === 'remote' ? `remote · ${job.instances} instance${job.instances === 1 ? '' : 's'}` : 'engine'}
            </Badge>
          </div>
          <p className="job-detail-module data-mono" title={job.module_id}>
            {job.module_id}
          </p>
          {job.description && <p className="job-detail-description">{job.description}</p>}
        </div>
        <button type="button" className="data-button data-button-primary" onClick={onRun}>
          <Play size={14} aria-hidden="true" /> Run now
        </button>
      </header>

      {job.last_run && FAILED.includes(job.last_run.status) && (
        <Notice tone="danger">
          <AlertTriangle size={14} aria-hidden="true" />
          <span className="job-last-failure">
            Last run {statusLabel(job.last_run.status).toLowerCase()} <RelativeTime iso={job.last_run.started_at} />
            {job.last_run.error && <code className="data-mono">{job.last_run.error}</code>}
          </span>
          <button type="button" className="data-text-button" onClick={() => job.last_run && onOpenRun(job.last_run)}>
            Open the run
          </button>
        </Notice>
      )}

      <div className="job-cards">
        <Card title="Schedule">
          {job.triggers.length ? (
            <ul className="job-triggers">
              {job.triggers.map((t, i) => {
                const Icon = KIND_ICONS[t.kind] ?? Clock;
                return (
                  <li key={i} className="job-trigger">
                    <Icon size={14} aria-hidden="true" className="job-trigger-icon" />
                    <div className="job-trigger-body">
                      <p className="job-trigger-summary">{t.summary}</p>
                      <p className="job-trigger-spec">
                        <code className="data-mono">{t.spec}</code>
                        {t.time_zone && <span className="data-muted"> · {t.time_zone}</span>}
                      </p>
                    </div>
                    {t.kind !== 'event' && (
                      <span className="job-trigger-next">
                        <span className="data-muted">next</span>
                        <Countdown iso={t.next_at} />
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="job-card-empty">
              <Hand size={14} aria-hidden="true" /> No trigger: runs only when started (Run now, the SDK, or another job).
            </p>
          )}
        </Card>
        <Card title="Health">
          <div className="job-health">
            <span className={`job-health-rate${h.rate !== null && h.rate < 0.8 ? ' job-health-bad' : ''}`}>
              {h.rate === null ? '—' : `${Math.round(h.rate * 100)}%`}
            </span>
            <span className="data-muted">
              {h.total ? `success over the last ${h.total} finished` : 'no finished run yet'}
            </span>
          </div>
          <RunStrip runs={job.recent} onOpen={onOpenRun} />
          <dl className="job-stats">
            <div>
              <dt>Failures</dt>
              <dd>{h.failed}</dd>
            </div>
            <div>
              <dt>Avg duration</dt>
              <dd>{formatMs(h.averageMs)}</dd>
            </div>
          </dl>
        </Card>
        <Card title="Now">
          <dl className="job-stats">
            <div>
              <dt>Running</dt>
              <dd>{job.running}</dd>
            </div>
            <div>
              <dt>Queued</dt>
              <dd>{job.queued ?? '—'}</dd>
            </div>
            <div>
              <dt>Delivered, not acked</dt>
              <dd>{job.in_flight ?? '—'}</dd>
            </div>
          </dl>
        </Card>
        <Card title="Settings">
          <dl className="job-stats">
            <div>
              <dt>Concurrency</dt>
              <dd>{job.max_concurrency}</dd>
            </div>
            <div>
              <dt>Attempts</dt>
              <dd>{job.max_attempts}</dd>
            </div>
            <div>
              <dt>Timeout</dt>
              <dd>{job.timeout_seconds ? formatMs(job.timeout_seconds * 1000) : 'none'}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <section className="job-runs">
        <div className="job-runs-head">
          <h3 className="job-card-title">Runs</h3>
          <StatusFilter value={statuses} onChange={onStatuses} />
        </div>
        <RunsList runs={runs} selected={selectedRun} showJob={false} onOpen={onOpenRun} />
      </section>
    </div>
  );
}
