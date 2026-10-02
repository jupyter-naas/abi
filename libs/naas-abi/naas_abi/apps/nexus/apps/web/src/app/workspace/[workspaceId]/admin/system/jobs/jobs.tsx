'use client';

/**
 * The Jobs tab: every module job with its schedule, next tick and recent runs; a
 * run feed across jobs; and each run's timeline, logs, payload, result and trace.
 * Run now, re-run and cancel are audited by the API.
 */
import '../data/data.css';
import './jobs.css';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import * as Tooltip from '@radix-ui/react-tooltip';
import { ChevronRight, RefreshCw, Search, Workflow } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { plural } from '../data/data-model';
import { Hint, IconTile, Kbd, Notice } from '../data/data-ui';
import { ToastStack, useToasts } from '../data/toasts';
import { createTracesApi, type TracesApi } from '../traces/traces-api';
import { createJobsApi, type JobsApi } from './jobs-api';
import {
  FAILED,
  decodeJobsLocation,
  encodeJobsLocation,
  filterJobs,
  isActive,
  splitKey,
  type JobsLocation,
} from './jobs-model';
import type { JobView, JobsOverview, RunDetail, RunSummary } from './jobs-types';
import { JobDetail } from './job-detail';
import { JobsTable } from './jobs-table';
import { CancelDialog, TriggerDialog } from './run-dialogs';
import { RunPanel } from './run-panel';
import { RunsList, StatusFilter } from './runs-list';

const OVERVIEW_MS = 5000;
const RUNS_MS = 5000;
const LIVE_RUN_MS = 1500;
const PAGE = 50;

/** Calls ``fn`` now and every ``ms`` while the page is visible and ``enabled``. */
function usePoll(fn: () => void, ms: number, enabled: boolean, deps: unknown[]) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!enabled) return;
    saved.current();
    const timer = window.setInterval(() => {
      if (!document.hidden) saved.current();
    }, ms);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, enabled, ...deps]);
}

interface TriggerRequest {
  job: string;
  moduleId: string;
  payload: unknown;
  rerun: boolean;
}

export function JobsTab({
  api: injected,
  tracesApi: injectedTraces,
  nonce = 0,
}: {
  api?: JobsApi;
  tracesApi?: TracesApi;
  nonce?: number;
}) {
  const api = useMemo(() => injected ?? createJobsApi(), [injected]);
  const tracesApi = useMemo(() => injectedTraces ?? createTracesApi(), [injectedTraces]);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [location, setLocation] = useState<JobsLocation>(() =>
    decodeJobsLocation(new URLSearchParams(params.toString())),
  );
  const [overview, setOverview] = useState<JobsOverview | null>(null);
  const [overviewFailure, setOverviewFailure] = useState<Failure | null>(null);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [runFailure, setRunFailure] = useState<Failure | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [triggering, setTriggering] = useState<TriggerRequest | null>(null);
  const [cancelling, setCancelling] = useState<RunSummary | null>(null);
  const { toasts, push, dismiss } = useToasts();
  const searchRef = useRef<HTMLInputElement>(null);
  const [reloads, setReloads] = useState(0);
  const loadedMore = useRef(false);

  // The location lives in the URL: a refresh or a shared link lands in the same place.
  useEffect(() => {
    const encoded = encodeJobsLocation(location, new URLSearchParams(params.toString()));
    if (encoded.toString() !== params.toString()) router.replace(`${pathname}?${encoded.toString()}`, { scroll: false });
  }, [location]); // eslint-disable-line react-hooks/exhaustive-deps

  const go = useCallback((patch: Partial<JobsLocation>) => setLocation((l) => ({ ...l, ...patch })), []);

  const job = useMemo(
    () => (location.job ? (overview?.jobs.find((j) => j.key === location.job) ?? null) : null),
    [overview, location.job],
  );

  usePoll(
    () => {
      void api.overview().then((result) => {
        if (result.ok) {
          setOverview(result.data);
          setOverviewFailure(null);
        } else setOverviewFailure(result);
      });
    },
    OVERVIEW_MS,
    true,
    [api, nonce, reloads],
  );

  const runFilter = useMemo(() => {
    if (location.job) {
      const [module, name] = splitKey(location.job);
      return { module, job: name, statuses: location.statuses };
    }
    return { statuses: location.statuses };
  }, [location.job, location.statuses]);
  const showRuns = location.view === 'runs' || Boolean(location.job);

  useEffect(() => {
    setRuns(null);
    loadedMore.current = false;
  }, [runFilter]);
  usePoll(
    () => {
      void api.runs({ ...runFilter, limit: PAGE }).then((result) => {
        if (!result.ok) return;
        if (!loadedMore.current) {
          setRuns(result.data.runs);
          setNext(result.data.next);
          return;
        }
        // Older pages stay below the refreshed first page.
        setRuns((prev) => {
          const fresh = new Set(result.data.runs.map((r) => r.key));
          return [...result.data.runs, ...(prev ?? []).filter((r) => !fresh.has(r.key))];
        });
      });
    },
    RUNS_MS,
    showRuns,
    [api, runFilter, nonce, reloads],
  );

  const loadMore = () => {
    if (!next) return;
    loadedMore.current = true;
    void api.runs({ ...runFilter, before: next, limit: PAGE }).then((result) => {
      if (!result.ok) return;
      setRuns((prev) => {
        const seen = new Set((prev ?? []).map((r) => r.key));
        return [...(prev ?? []), ...result.data.runs.filter((r) => !seen.has(r.key))];
      });
      setNext(result.data.next);
    });
  };

  // The open run, refreshed while it is live (or queued after Run now).
  const runKey = location.run;
  const liveRun = Boolean(pending) || (detail ? isActive(detail.status) : true);
  useEffect(() => {
    setDetail(null);
    setRunFailure(null);
  }, [runKey]);
  usePoll(
    () => {
      if (!runKey) return;
      const [module, id] = splitKey(runKey);
      void api.run(module, id).then((result) => {
        if (result.ok) {
          setDetail(result.data);
          setRunFailure(null);
          if (pending === runKey) setPending(null);
        } else if (result.status !== 404 || pending !== runKey) setRunFailure(result);
      });
    },
    LIVE_RUN_MS,
    Boolean(runKey) && liveRun,
    [api, runKey, pending],
  );
  // A finished run still loads once.
  useEffect(() => {
    if (!runKey || liveRun) return;
    const [module, id] = splitKey(runKey);
    void api.run(module, id).then((result) => result.ok && setDetail(result.data));
  }, [api, runKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = useMemo(() => {
    if (!runKey) return null;
    const all = [...(runs ?? []), ...(overview?.jobs.flatMap((j) => j.recent) ?? [])];
    return all.find((r) => r.key === runKey) ?? null;
  }, [runKey, runs, overview]);

  const openRun = (run: RunSummary) => {
    setPending(null);
    go({ run: run.key });
  };

  const startTrigger = (j: JobView) => setTriggering({ job: j.name, moduleId: j.module_id, payload: {}, rerun: false });

  const submitTrigger = async (payload: Record<string, unknown>) => {
    if (!triggering) return null;
    const result = await api.trigger(triggering.moduleId, triggering.job, payload);
    if (!result.ok) return result;
    setTriggering(null);
    setPending(result.data.key);
    go({ run: result.data.key });
    push({ tone: 'success', title: `Started ${triggering.job}`, detail: 'Recorded in the audit log' });
    return null;
  };

  const submitCancel = async () => {
    if (!cancelling) return null;
    const result = await api.cancel(cancelling.module_id, cancelling.run_id);
    if (!result.ok) return result;
    push({ tone: 'success', title: `Cancellation sent to ${cancelling.job}`, detail: 'The run stops at its next check' });
    setCancelling(null);
    return null;
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target instanceof HTMLElement && (['INPUT', 'TEXTAREA'].includes(target.tagName) || target.closest('[role="dialog"], .monaco-editor'))) return;
      if (triggering || cancelling) return;
      if (event.key === 'Escape') {
        if (location.run) go({ run: null });
        else if (location.job) go({ job: null });
      } else if (event.key === '/') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const jobs = overview?.jobs ?? [];
  const running = jobs.reduce((n, j) => n + j.running, 0);
  const failing = jobs.filter((j) => j.last_run && FAILED.includes(j.last_run.status)).length;
  const down = Object.entries(overview?.sources ?? {}).filter(([, s]) => !s.available);

  return (
    <Tooltip.Provider>
      <div className="data-explorer jobs-root">
        <section className="data-main jobs-main" aria-label="Jobs">
          <header className="data-service-header">
            <IconTile icon={Workflow} size="lg" />
            <div className="data-service-heading">
              <div className="data-service-title-row">
                <h2 className="data-service-title">Jobs</h2>
                {overview && <span className="data-badge data-badge-mono">{overview.project}</span>}
              </div>
              <p className="data-service-description">
                {overview
                  ? `${plural(jobs.length, 'job', 'jobs')} · ${running} running${failing ? ` · ${failing} failing` : ''}`
                  : 'Schedules, triggers and every run of module jobs.'}
              </p>
            </div>
            <div className="data-service-actions">
              <div className="data-segmented" role="tablist" aria-label="Jobs views">
                {(['jobs', 'runs'] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    role="tab"
                    aria-selected={location.view === v && !location.job}
                    className={location.view === v && !location.job ? 'data-segment data-segment-active' : 'data-segment'}
                    onClick={() => go({ view: v, job: null })}
                  >
                    {v === 'jobs' ? 'Jobs' : 'Runs'}
                  </button>
                ))}
              </div>
              <Hint label="Refresh">
                <button
                  type="button"
                  className="data-icon-button data-icon-button-bordered"
                  aria-label="Refresh"
                  onClick={() => setReloads((n) => n + 1)}
                >
                  <RefreshCw size={14} aria-hidden="true" />
                </button>
              </Hint>
            </div>
          </header>
          <div className="data-toolbar">
            <nav className="data-crumbs" aria-label="Path">
              <span className="data-crumb">
                {location.job ? (
                  <button type="button" className="data-crumb-link" onClick={() => go({ job: null })}>
                    {location.view === 'runs' ? 'Runs' : 'Jobs'}
                  </button>
                ) : (
                  <span className="data-crumb-current">{location.view === 'runs' ? 'All runs' : 'All jobs'}</span>
                )}
              </span>
              {location.job && (
                <span className="data-crumb">
                  <ChevronRight size={12} aria-hidden="true" className="data-crumb-sep" />
                  <span className="data-crumb-current">{job?.name ?? splitKey(location.job)[1]}</span>
                </span>
              )}
            </nav>
            {location.view === 'runs' && !location.job && (
              <StatusFilter value={location.statuses} onChange={(statuses) => go({ statuses })} />
            )}
            {location.view === 'jobs' && !location.job && (
              <label className="data-search">
                <Search size={14} aria-hidden="true" />
                <input
                  ref={searchRef}
                  className="data-search-input"
                  placeholder="Filter jobs"
                  aria-label="Filter jobs"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {!search && <Kbd>/</Kbd>}
              </label>
            )}
          </div>
          <div className="data-browser">
            {overviewFailure && <Notice tone="danger">{overviewFailure.reason}</Notice>}
            {down.map(([source, status]) => (
              <Notice key={source} tone="warn">
                <strong>{source}</strong>: {status.reason}
              </Notice>
            ))}
            {location.job ? (
              job ? (
                <JobDetail
                  job={job}
                  runs={runs}
                  statuses={location.statuses}
                  selectedRun={location.run}
                  onStatuses={(statuses) => go({ statuses })}
                  onOpenRun={openRun}
                  onRun={() => startTrigger(job)}
                />
              ) : overview ? (
                <Notice tone="warn">This job is not declared by any loaded or registered module anymore.</Notice>
              ) : null
            ) : location.view === 'runs' ? (
              <>
                <RunsList runs={runs} selected={location.run} showJob onOpen={openRun} />
                {next && runs && (
                  <div className="data-load-more">
                    <button type="button" className="data-button" onClick={loadMore}>
                      Load older runs
                    </button>
                  </div>
                )}
              </>
            ) : overview ? (
              <JobsTable
                jobs={filterJobs(jobs, search)}
                selected={null}
                onSelect={(j) => go({ job: j.key, statuses: [] })}
                onRun={startTrigger}
                onOpenRun={openRun}
              />
            ) : (
              <p className="data-empty-text jobs-loading">Loading jobs…</p>
            )}
          </div>
        </section>
        {location.run && (
          <RunPanel
            summary={summary}
            detail={detail}
            pending={pending === location.run}
            failure={runFailure}
            onClose={() => go({ run: null })}
            onCancel={setCancelling}
            onRerun={(run, payload) => setTriggering({ job: run.job, moduleId: run.module_id, payload, rerun: true })}
            onOpenJob={(run) => go({ job: `${run.module_id}/${run.job}` })}
            tracesApi={tracesApi}
            onOpenTrace={(traceId) => router.push(`${pathname}?tab=traces&trace=${encodeURIComponent(traceId)}`)}
          />
        )}
        {triggering && (
          <TriggerDialog
            job={triggering.job}
            moduleId={triggering.moduleId}
            initialPayload={triggering.payload}
            rerun={triggering.rerun}
            onSubmit={submitTrigger}
            onClose={() => setTriggering(null)}
          />
        )}
        {cancelling && <CancelDialog run={cancelling} onConfirm={submitCancel} onClose={() => setCancelling(null)} />}
        <ToastStack toasts={toasts} dismiss={dismiss} />
      </div>
    </Tooltip.Provider>
  );
}
