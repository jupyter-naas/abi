'use client';

/**
 * The Agents tab: every remote agent run across the modules that host agents,
 * newest first, and one run with its caller, owner, events and trace. A running
 * run can be cancelled; the API audits it and the owning host stops it.
 */
import '../data/data.css';
import '../jobs/jobs.css';
import './agents.css';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Tooltip from '@radix-ui/react-tooltip';
import { AlertTriangle, Bot, MessageSquare, RefreshCw, Square, Waypoints, X } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { absoluteTime, plural } from '../data/data-model';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/dialogs';
import { EmptyState } from '@/components/ui/empty-state';
import { Notice } from '@/components/ui/notice';
import { Loading } from '@/components/ui/spinner';
import { Tabs } from '@/components/ui/tabs';
import { toast } from '@/components/ui/toast';
import { CopyButton, Property, Hint, RelativeTime, StatusPill, useNow } from '../data/data-ui';
import { formatMs, moduleLabel } from '../jobs/jobs-model';
import { createAgentsApi, type AgentsApi } from './agents-api';
import { STATUS_FILTERS, isActive, isCancellable, runDuration, splitKey, statusLabel, statusTone } from './agents-model';
import type { AgentRunDetail, AgentRunSummary } from './agents-types';
import { systemTracePath } from '../system-tabs';
import { usePoll } from '../use-poll';

const RUNS_MS = 5000;
const LIVE_RUN_MS = 1500;
const PAGE = 50;

function AgentStatus({ status }: { status: string }) {
  return <StatusPill tone={statusTone(status)} label={statusLabel(status)} pulse={isActive(status)} />;
}

function Duration({ run }: { run: AgentRunSummary }) {
  const now = useNow(isActive(run.status) ? 1000 : 60_000);
  return <span className="data-num">{formatMs(runDuration(run, now))}</span>;
}

function StatusFilter({ value, onChange }: { value: string[]; onChange: (statuses: string[]) => void }) {
  const active = STATUS_FILTERS.find((f) => f.statuses.join(',') === value.join(','))?.id ?? 'all';
  return (
    <Tabs
      variant="segmented"
      label="Run status"
      value={active}
      onChange={(id) => onChange(STATUS_FILTERS.find((f) => f.id === id)?.statuses ?? [])}
      items={STATUS_FILTERS}
    />
  );
}

function RunsList({
  runs,
  selected,
  onOpen,
}: {
  runs: AgentRunSummary[] | null;
  selected: string | null;
  onOpen: (run: AgentRunSummary) => void;
}) {
  if (runs === null) return <Loading />;
  if (!runs.length) {
    return (
      <EmptyState
        icon={<Bot size={22} strokeWidth={1.5} />}
        title="No agent runs match"
        description="Runs appear here when a caller (Nexus, another module) invokes an agent a module hosts over NATS."
      />
    );
  }
  return (
    <div className="runs-list agents-list" role="listbox" aria-label="Agent runs">
      <div className="runs-head" aria-hidden="true">
        <span>Status</span>
        <span>Agent</span>
        <span>Invocation</span>
        <span>Caller</span>
        <span>Submitted</span>
        <span className="data-align-end">Duration</span>
      </div>
      {runs.map((run) => (
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
            <AgentStatus status={run.status} />
          </span>
          <span className="runs-job">
            <span className="runs-job-name">{run.agent}</span>
            <span className="data-muted" title={run.module_id}>
              {moduleLabel(run.module_id)}
            </span>
          </span>
          <span className="data-mono runs-id" title={run.invocation_id}>
            {run.invocation_id}
          </span>
          <span className="data-mono agents-caller" title={run.caller}>
            {run.caller || '—'}
          </span>
          <span className="runs-when" title={absoluteTime(run.submitted_at)}>
            <RelativeTime iso={run.submitted_at} />
          </span>
          <span className="data-align-end">
            <Duration run={run} />
          </span>
        </div>
      ))}
    </div>
  );
}

function RunPanel({
  summary,
  detail,
  failure,
  onClose,
  onCancel,
  onOpenTrace,
}: {
  summary: AgentRunSummary | null;
  detail: AgentRunDetail | null;
  failure: Failure | null;
  onClose: () => void;
  onCancel: (run: AgentRunSummary) => void;
  onOpenTrace: (traceId: string) => void;
}) {
  const run = detail ?? summary;
  if (!run) {
    return (
      <aside className="data-inspector run-panel" aria-label="Selected agent run">
        {failure ? <Notice tone="error">{failure.reason}</Notice> : <Loading />}
      </aside>
    );
  }
  return (
    <aside className="data-inspector run-panel" aria-label="Selected agent run">
      <header className="data-inspector-header">
        <div className="data-inspector-top">
          <span className="data-inspector-icon">
            <Bot size={17} aria-hidden="true" />
          </span>
          <div className="data-inspector-heading">
            <h3 className="data-inspector-title">{run.agent}</h3>
            <div className="data-inspector-id">
              <code className="data-mono">{run.invocation_id}</code>
              <CopyButton value={run.key} label="Copy run key" />
            </div>
          </div>
          <Hint label="Close" shortcut="Esc">
            <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
              <X size={16} aria-hidden="true" />
            </Button>
          </Hint>
        </div>
        <div className="data-inspector-facts">
          <AgentStatus status={run.status} />
          <span className="data-fact">
            <span className="data-fact-label">Module</span>
            <span className="data-fact-value" title={run.module_id}>
              {moduleLabel(run.module_id)}
            </span>
          </span>
          <span className="data-fact">
            <span className="data-fact-label">Took</span>
            <span className="data-fact-value">
              <Duration run={run} />
            </span>
          </span>
        </div>
        {(run.error_code || run.error_message) && (
          <Notice
            tone={run.status === 'CANCELLED' ? 'info' : 'error'}
            icon={<AlertTriangle size={14} aria-hidden="true" />}
          >
            <span className="run-error">
              {run.error_code}
              {run.error_message ? ` · ${run.error_message}` : ''}
            </span>
          </Notice>
        )}
        {failure && <Notice tone="error">{failure.reason}</Notice>}
      </header>
      <div className="data-inspector-body">
        <dl className="data-fields">
          <Property label="Caller">
            <code className="data-mono">{run.caller || '—'}</code>
          </Property>
          <Property label="Thread">
            <code className="data-mono">{run.thread_id || '—'}</code>
          </Property>
          <Property label="Owner instance">
            <code className="data-mono">{run.owner || '—'}</code>
          </Property>
          <Property label="Submitted">{absoluteTime(run.submitted_at)}</Property>
          <Property label="Finished">{run.finished_at ? absoluteTime(run.finished_at) : '—'}</Property>
        </dl>
        <h4 className="agents-events-title">
          Events <span className="jobs-tab-count">{run.events}</span>
        </h4>
        {!detail ? (
          <Loading />
        ) : detail.event_list.length ? (
          <ol className="agents-events">
            {detail.event_list.map((event) => (
              <li key={event.sequence} className="agents-event">
                <span className="agents-event-head">
                  <span className="data-num data-muted">{event.sequence}</span>
                  <Badge>{event.event}</Badge>
                </span>
                <pre className="agents-event-text">
                  {event.preview}
                  {event.truncated ? '…' : ''}
                </pre>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState
            icon={<MessageSquare size={22} strokeWidth={1.5} />}
            title="No events yet"
            description="Streamed runs record each event as the agent emits it."
          />
        )}
      </div>
      <footer className="data-inspector-actions">
        {run.trace_id ? (
          <Button variant="secondary" size="sm" onClick={() => onOpenTrace(run.trace_id)}>
            <Waypoints size={14} aria-hidden="true" /> Open trace
          </Button>
        ) : null}
        <span className="data-spacer" />
        {isCancellable(run.status) && (
          <Hint label="Ask the owning host to stop it">
            <Button variant="destructive-ghost" size="sm" onClick={() => onCancel(run)}>
              <Square size={13} aria-hidden="true" /> Cancel
            </Button>
          </Hint>
        )}
      </footer>
    </aside>
  );
}

function CancelDialog({
  run,
  onConfirm,
  onClose,
}: {
  run: AgentRunSummary;
  onConfirm: () => Promise<Failure | null>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const submit = async () => {
    setBusy(true);
    const result = await onConfirm();
    setBusy(false);
    if (result) setFailure(result);
  };
  return (
    <ConfirmDialog
      open
      title={`Cancel ${run.agent}?`}
      confirmLabel={busy ? 'Cancelling…' : 'Cancel run'}
      cancelLabel="Keep running"
      busy={busy}
      error={failure?.reason}
      onConfirm={submit}
      onCancel={onClose}
    >
      <p className="text-muted-foreground">
        <code className="data-mono">{run.invocation_id}</code>: the host that owns this run (
        <code className="data-mono">{run.owner}</code>) stops it at its next step and records it as cancelled. Whatever
        the agent already did (tool calls, writes) is not undone. Recorded in the audit log.
      </p>
    </ConfirmDialog>
  );
}

export function AgentsTab({ api: injected, nonce = 0 }: { api?: AgentsApi; nonce?: number }) {
  const api = useMemo(() => injected ?? createAgentsApi(), [injected]);
  const router = useRouter();
  const [statuses, setStatuses] = useState<string[]>([]);
  const [runs, setRuns] = useState<AgentRunSummary[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentRunDetail | null>(null);
  const [runFailure, setRunFailure] = useState<Failure | null>(null);
  const [cancelling, setCancelling] = useState<AgentRunSummary | null>(null);
  const [reloads, setReloads] = useState(0);
  const loadedMore = useRef(false);

  useEffect(() => {
    setRuns(null);
    loadedMore.current = false;
  }, [statuses]);
  usePoll(
    (signal) =>
      api.runs({ statuses, limit: PAGE }, signal).then((result) => {
        if (signal.aborted) return;
        if (!result.ok) {
          setFailure(result);
          setRuns((prev) => prev ?? []);
          return;
        }
        setFailure(null);
        if (!loadedMore.current) {
          setRuns(result.data.runs);
          setNext(result.data.next);
          return;
        }
        setRuns((prev) => {
          const fresh = new Set(result.data.runs.map((r) => r.key));
          return [...result.data.runs, ...(prev ?? []).filter((r) => !fresh.has(r.key))];
        });
      }),
    RUNS_MS,
    true,
    [api, statuses, nonce, reloads],
  );

  const loadMore = () => {
    if (!next) return;
    loadedMore.current = true;
    void api.runs({ statuses, before: next, limit: PAGE }).then((result) => {
      if (!result.ok) return;
      setRuns((prev) => {
        const seen = new Set((prev ?? []).map((r) => r.key));
        return [...(prev ?? []), ...result.data.runs.filter((r) => !seen.has(r.key))];
      });
      setNext(result.data.next);
    });
  };

  const summary = useMemo(() => runs?.find((r) => r.key === selected) ?? null, [runs, selected]);
  const live = detail ? isActive(detail.status) : true;
  useEffect(() => {
    setDetail(null);
    setRunFailure(null);
  }, [selected]);
  usePoll(
    (signal) => {
      if (!selected) return;
      const [module, id] = splitKey(selected);
      return api.run(module, id, signal).then((result) => {
        if (signal.aborted) return;
        if (result.ok) {
          setDetail(result.data);
          setRunFailure(null);
        } else setRunFailure(result);
      });
    },
    LIVE_RUN_MS,
    Boolean(selected) && live,
    [api, selected],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && selected && !cancelling) setSelected(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const submitCancel = async () => {
    if (!cancelling) return null;
    const result = await api.cancel(cancelling.module_id, cancelling.run_id);
    if (!result.ok) return result;
    toast({ tone: 'success', title: `Cancellation sent to ${cancelling.agent}`, detail: 'Recorded in the audit log' });
    setCancelling(null);
    setReloads((n) => n + 1);
    return null;
  };

  const running = (runs ?? []).filter((r) => isActive(r.status)).length;

  return (
    <Tooltip.Provider>
      <div className="data-explorer jobs-root">
        <section className="data-main jobs-main" aria-label="Agent runs">
          <header className="data-service-header">
            {/* The page's frame holds the title; this line is the summary. */}
            <div className="data-service-heading">
              <p className="data-service-description">
                {runs
                  ? `${plural(runs.length, 'run', 'runs')} shown · ${running} running`
                  : 'Remote agent runs across the modules that host agents.'}
              </p>
            </div>
            <div className="data-service-actions">
              <Hint label="Refresh">
                <Button variant="secondary" size="icon" aria-label="Refresh" onClick={() => setReloads((n) => n + 1)}>
                  <RefreshCw size={14} aria-hidden="true" />
                </Button>
              </Hint>
            </div>
          </header>
          <div className="data-toolbar">
            <span className="data-crumb-current">All runs</span>
            <StatusFilter value={statuses} onChange={setStatuses} />
          </div>
          <div className="data-browser">
            {failure && (
              <Notice tone="warning" className="mx-6 mt-3">
                {failure.source && <strong>{failure.source}</strong>}
                {failure.source ? ': ' : ''}
                {failure.reason}
              </Notice>
            )}
            <RunsList runs={runs} selected={selected} onOpen={(run) => setSelected(run.key)} />
            {next && runs && (
              <div className="data-load-more">
                <Button variant="secondary" size="sm" onClick={loadMore}>
                  Load older runs
                </Button>
              </div>
            )}
          </div>
        </section>
        {selected && (
          <RunPanel
            summary={summary}
            detail={detail}
            failure={runFailure}
            onClose={() => setSelected(null)}
            onCancel={setCancelling}
            onOpenTrace={(traceId) => router.push(systemTracePath(traceId))}
          />
        )}
        {cancelling && <CancelDialog run={cancelling} onConfirm={submitCancel} onClose={() => setCancelling(null)} />}
      </div>
    </Tooltip.Provider>
  );
}
