'use client';

/** One run: how it was triggered, when it started and ended, its logs, data and trace. */
import { useEffect, useState } from 'react';
import { AlertTriangle, Hourglass, Play, ScrollText, Square, Waypoints, X } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { absoluteTime } from '../data/data-model';
import { Badge, CopyButton, EmptyState, Hint, Notice, RelativeTime, SkeletonRows } from '../data/data-ui';
import { JsonTree } from '../data/viewers/json-tree';
import type { TracesApi } from '../traces/traces-api';
import { TraceView } from '../traces/trace-view';
import { formatMs, isActive, moduleLabel, startDelay } from './jobs-model';
import type { RunDetail, RunSummary } from './jobs-types';
import { RunDuration, RunStatus, TriggerTag } from './jobs-ui';

type Tab = 'logs' | 'payload' | 'result' | 'trace';

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return true;
  if (typeof value === 'object') return Object.keys(value as object).length === 0;
  return false;
}

function Timeline({ run }: { run: RunSummary }) {
  const delay = startDelay(run);
  const live = isActive(run.status);
  return (
    <ol className="run-timeline">
      <li className="run-step run-step-done">
        <span className="run-step-dot" aria-hidden="true" />
        <div>
          <p className="run-step-title">
            Triggered <TriggerTag kind={run.trigger.kind} />
          </p>
          <p className="run-step-meta">
            {run.fired_at ? (
              <>
                {absoluteTime(run.fired_at)} · <RelativeTime iso={run.fired_at} />
              </>
            ) : (
              'Time not recorded'
            )}
            {run.trigger.scheduler && (
              <span className="data-mono run-step-scheduler" title={run.trigger.scheduler}>
                {run.trigger.scheduler}
              </span>
            )}
          </p>
        </div>
      </li>
      <li className={`run-step${run.started_at ? ' run-step-done' : ''}`}>
        <span className="run-step-dot" aria-hidden="true" />
        <div>
          <p className="run-step-title">
            Started{run.attempt > 1 ? ` · attempt ${run.attempt} of ${run.max_attempts}` : ''}
          </p>
          <p className="run-step-meta">
            {run.started_at ? absoluteTime(run.started_at) : 'Waiting for a host'}
            {delay !== null && <> · waited {formatMs(delay)}</>}
            {run.instance && (
              <span className="data-mono run-step-scheduler" title={run.instance}>
                on {run.instance}
              </span>
            )}
          </p>
        </div>
      </li>
      <li className={`run-step${live ? ' run-step-live' : ' run-step-done'}`}>
        <span className="run-step-dot" aria-hidden="true" />
        <div>
          <p className="run-step-title">
            {live ? 'Running for ' : 'Finished · '}
            <RunDuration run={run} />
          </p>
          <p className="run-step-meta">{run.finished_at ? absoluteTime(run.finished_at) : live ? 'Still running' : '—'}</p>
        </div>
      </li>
    </ol>
  );
}

function Logs({ lines }: { lines: string[] }) {
  if (!lines.length) {
    return (
      <EmptyState icon={ScrollText} title="No log lines">
        Lines a job writes with <code className="data-mono">ctx.log(...)</code> show up here (up to 200 per run).
      </EmptyState>
    );
  }
  return (
    <div className="run-logs">
      <div className="run-logs-toolbar">
        <span className="data-muted">{lines.length} lines</span>
        <span className="data-spacer" />
        <CopyButton value={lines.join('\n')} label="Copy logs" />
      </div>
      <ol className="run-logs-lines">
        {lines.map((line, i) => (
          <li key={i}>
            <span className="run-logs-number" aria-hidden="true">
              {i + 1}
            </span>
            <span className="run-logs-text">{line}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function RunPanel({
  summary,
  detail,
  pending,
  failure,
  onClose,
  onCancel,
  onRerun,
  onOpenJob,
  tracesApi,
  onOpenTrace,
}: {
  summary: RunSummary | null;
  detail: RunDetail | null;
  /** Triggered from here and not picked up by a host yet. */
  pending: boolean;
  failure: Failure | null;
  onClose: () => void;
  onCancel: (run: RunSummary) => void;
  onRerun: (run: RunSummary, payload: unknown) => void;
  onOpenJob: (run: RunSummary) => void;
  tracesApi: TracesApi;
  onOpenTrace: (traceId: string) => void;
}) {
  const run = detail ?? summary;
  const [tab, setTab] = useState<Tab>('logs');
  useEffect(() => setTab('logs'), [run?.key]);

  if (pending && !run) {
    return (
      <aside className="data-inspector run-panel" aria-label="Selected run">
        <div className="data-inspector-loading">
          <EmptyState icon={Hourglass} title="Queued">
            The trigger is on the bus; the run appears as soon as a host picks it up.
          </EmptyState>
        </div>
      </aside>
    );
  }
  if (!run) {
    return (
      <aside className="data-inspector run-panel" aria-label="Selected run">
        <div className="data-inspector-loading">
          {failure ? (
            <EmptyState icon={AlertTriangle} title={failure.status === 404 ? 'Run not found' : 'Could not open the run'}>
              {failure.reason}
            </EmptyState>
          ) : (
            <SkeletonRows rows={4} />
          )}
        </div>
      </aside>
    );
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'logs', label: 'Logs', count: detail?.logs.length },
    { id: 'payload', label: 'Payload' },
    { id: 'result', label: run.status === 'SUCCEEDED' ? 'Result' : 'Output' },
    { id: 'trace', label: 'Trace' },
  ];

  return (
    <aside className={tab === 'trace' ? 'data-inspector run-panel run-panel-wide' : 'data-inspector run-panel'} aria-label="Selected run">
      <header className="data-inspector-header">
        <div className="data-inspector-top">
          <span className="data-inspector-icon">
            <Play size={17} aria-hidden="true" />
          </span>
          <div className="data-inspector-heading">
            <h3 className="data-inspector-title">
              <button type="button" className="data-link run-panel-job" onClick={() => onOpenJob(run)}>
                {run.job}
              </button>
            </h3>
            <div className="data-inspector-id">
              <code className="data-mono">{run.run_id}</code>
              <CopyButton value={run.key} label="Copy run key" />
            </div>
          </div>
          <Hint label="Close" shortcut="Esc">
            <button type="button" className="data-icon-button" aria-label="Close" onClick={onClose}>
              <X size={16} aria-hidden="true" />
            </button>
          </Hint>
        </div>
        <div className="data-inspector-facts">
          <RunStatus status={run.status} />
          <span className="data-fact">
            <span className="data-fact-label">Module</span>
            <span className="data-fact-value" title={run.module_id}>
              {moduleLabel(run.module_id)}
            </span>
          </span>
          <span className="data-fact">
            <span className="data-fact-label">Attempt</span>
            <span className="data-fact-value">
              {run.attempt}/{run.max_attempts}
            </span>
          </span>
          {run.attempt > 1 && <Badge tone="warn">retried</Badge>}
        </div>
        <Timeline run={run} />
        {run.status === 'SKIPPED' && (
          <Notice tone="neutral">
            <span>Nothing to do{run.skip_reason ? `: ${run.skip_reason}` : ''}</span>
          </Notice>
        )}
        {run.error && (
          <Notice tone="danger">
            <AlertTriangle size={14} aria-hidden="true" />
            <span className="run-error">{run.error}</span>
          </Notice>
        )}
        <nav className="data-inspector-tabs" role="tablist" aria-label="Run views">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? 'data-inspector-tab data-inspector-tab-active' : 'data-inspector-tab'}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.count ? <span className="jobs-tab-count">{t.count}</span> : null}
            </button>
          ))}
        </nav>
      </header>
      <div className="data-inspector-body">
        {!detail ? (
          <SkeletonRows rows={4} />
        ) : tab === 'logs' ? (
          <Logs lines={detail.logs} />
        ) : tab === 'payload' ? (
          isEmpty(detail.payload) ? (
            <EmptyState icon={ScrollText} title="Empty payload">
              Schedules send none; Run now and events may.
            </EmptyState>
          ) : (
            <JsonTree value={detail.payload} />
          )
        ) : tab === 'result' ? (
          isEmpty(detail.result) ? (
            <EmptyState icon={ScrollText} title={run.status === 'SUCCEEDED' ? 'No result returned' : 'No output'}>
              {run.status === 'SUCCEEDED'
                ? 'The handler returned nothing (or None).'
                : 'Only successful runs record what the handler returned.'}
            </EmptyState>
          ) : typeof detail.result === 'object' ? (
            <JsonTree value={detail.result} />
          ) : (
            <pre className="data-text">{String(detail.result)}</pre>
          )
        ) : run.trace_id ? (
          <TraceView
            api={tracesApi}
            traceId={run.trace_id}
            compact
            uiUrl={detail.trace_url ? detail.trace_url.replace(/\/trace\/[^/]+$/, '') : null}
            onExpand={() => onOpenTrace(run.trace_id)}
            onOpenTrace={onOpenTrace}
          />
        ) : (
          <EmptyState icon={Waypoints} title="No trace">
            Tracing was off when this run started, or its host predates trace recording.
          </EmptyState>
        )}
      </div>
      <footer className="data-inspector-actions">
        <Hint label="Run the job again with the same payload">
          <button type="button" className="data-button" onClick={() => onRerun(run, detail?.payload ?? {})}>
            <Play size={14} aria-hidden="true" /> Re-run
          </button>
        </Hint>
        <span className="data-spacer" />
        {isActive(run.status) && (
          <Hint label="Ask the host to stop it; the job sees ctx.cancelled">
            <button type="button" className="data-button data-button-danger-ghost" onClick={() => onCancel(run)}>
              <Square size={13} aria-hidden="true" /> Cancel
            </button>
          </Hint>
        )}
      </footer>
    </aside>
  );
}
