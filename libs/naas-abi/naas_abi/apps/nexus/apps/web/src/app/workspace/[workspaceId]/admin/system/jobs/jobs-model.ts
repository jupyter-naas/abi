/** Pure helpers for the Jobs tab. */
import type { Tone } from '../data/data-ui';
import type { JobView, RunStep, RunSummary } from './jobs-types';

export const ACTIVE = ['RUNNING', 'RETRYING'];
export const FAILED = ['FAILED', 'TIMED_OUT'];

export const STATUS_LABELS: Record<string, string> = {
  QUEUED: 'Queued',
  RUNNING: 'Running',
  RETRYING: 'Retrying',
  SUCCEEDED: 'Succeeded',
  SKIPPED: 'Skipped',
  FAILED: 'Failed',
  TIMED_OUT: 'Timed out',
  CANCELLED: 'Cancelled',
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status.charAt(0) + status.slice(1).toLowerCase();
}

export function statusTone(status: string): Tone {
  if (status === 'SUCCEEDED') return 'success';
  if (status === 'RUNNING' || status === 'QUEUED') return 'info';
  if (status === 'RETRYING' || status === 'TIMED_OUT') return 'warn';
  if (status === 'FAILED') return 'danger';
  return 'neutral';
}

export const isActive = (status: string) => ACTIVE.includes(status);

export function triggerLabel(kind: string): string {
  if (kind === 'schedule') return 'Schedule';
  if (kind === 'manual') return 'Manual';
  if (kind === 'event') return 'Event';
  return kind || 'Unknown';
}

/** Milliseconds as "820 ms", "4.2 s", "3 min 05 s", "1 h 12 min". */
export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.max(0, Math.round(ms))} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`;
  const m = Math.floor(s / 60);
  const rest = Math.round(s % 60);
  if (m < 60) return rest ? `${m} min ${String(rest).padStart(2, '0')} s` : `${m} min`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min`;
}

const ms = (iso: string | null | undefined) => (iso ? Date.parse(iso) : NaN);

/** How long the run took, or has been running for (``now`` for live runs). */
export function runDuration(run: RunSummary, now: number = Date.now()): number | null {
  if (run.duration_ms !== null && run.duration_ms !== undefined) return run.duration_ms;
  const start = ms(run.started_at);
  if (Number.isNaN(start)) return null;
  const end = run.finished_at ? ms(run.finished_at) : isActive(run.status) ? now : NaN;
  return Number.isNaN(end) ? null : Math.max(0, end - start);
}

/** Time between the trigger firing and a host starting the run. */
export function startDelay(run: RunSummary): number | null {
  const fired = ms(run.fired_at);
  const start = ms(run.started_at);
  if (Number.isNaN(fired) || Number.isNaN(start)) return null;
  return Math.max(0, start - fired);
}

export interface Health {
  total: number;
  succeeded: number;
  failed: number;
  rate: number | null;
  averageMs: number | null;
}

/** Success rate and average duration over the finished runs given (runs that
 * had nothing to do, SKIPPED, count for neither). */
export function health(runs: RunSummary[]): Health {
  const finished = runs.filter((r) => !isActive(r.status) && r.status !== 'SKIPPED');
  const succeeded = finished.filter((r) => r.status === 'SUCCEEDED').length;
  const failed = finished.filter((r) => FAILED.includes(r.status)).length;
  const durations = finished.map((r) => r.duration_ms).filter((d): d is number => typeof d === 'number');
  return {
    total: finished.length,
    succeeded,
    failed,
    rate: finished.length ? succeeded / finished.length : null,
    averageMs: durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null,
  };
}

/** Jobs needing attention first: failing last run, then running, then by next tick. */
export function sortJobs(jobs: JobView[]): JobView[] {
  const rank = (j: JobView) => (j.last_run && FAILED.includes(j.last_run.status) ? 0 : j.running > 0 ? 1 : 2);
  return [...jobs].sort((a, b) => {
    const r = rank(a) - rank(b);
    if (r) return r;
    const na = a.next_at ? Date.parse(a.next_at) : Infinity;
    const nb = b.next_at ? Date.parse(b.next_at) : Infinity;
    if (na !== nb) return na - nb;
    return a.key.localeCompare(b.key);
  });
}

export type KindFilter = 'all' | 'job' | 'workflow';

export const isWorkflow = (job: Pick<JobView, 'kind'>) => job.kind === 'workflow';

export function filterJobs(jobs: JobView[], text: string, kind: KindFilter = 'all'): JobView[] {
  const needle = text.trim().toLowerCase();
  return jobs.filter(
    (j) =>
      (kind === 'all' || (j.kind ?? 'job') === kind) &&
      (!needle ||
        j.name.toLowerCase().includes(needle) ||
        j.module_id.toLowerCase().includes(needle) ||
        j.description.toLowerCase().includes(needle)),
  );
}

/** The last segment of a dotted module id, for compact labels. */
export function moduleLabel(moduleId: string): string {
  const parts = moduleId.split('.');
  return parts[parts.length - 1] || moduleId;
}

export type JobsView = 'jobs' | 'runs';

export interface JobsLocation {
  view: JobsView;
  job: string | null;
  run: string | null;
  statuses: string[];
  kind: KindFilter;
}

export function encodeJobsLocation(location: JobsLocation, params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params.toString());
  for (const key of ['view', 'job', 'run', 'status', 'kind']) next.delete(key);
  if (location.view !== 'jobs') next.set('view', location.view);
  if (location.kind !== 'all') next.set('kind', location.kind);
  if (location.job) next.set('job', location.job);
  if (location.run) next.set('run', location.run);
  if (location.statuses.length) next.set('status', location.statuses.join(','));
  return next;
}

export function decodeJobsLocation(params: URLSearchParams): JobsLocation {
  const view = params.get('view') === 'runs' ? 'runs' : 'jobs';
  const statuses = (params.get('status') ?? '').split(',').filter(Boolean);
  const kind = params.get('kind') === 'workflow' || params.get('kind') === 'job' ? (params.get('kind') as KindFilter) : 'all';
  return { view, job: params.get('job'), run: params.get('run'), statuses, kind };
}

/** "<module_id>/<rest>" split on the first "/" (module ids have no "/"). */
export function splitKey(key: string): [string, string] {
  const at = key.indexOf('/');
  return at < 0 ? [key, ''] : [key.slice(0, at), key.slice(at + 1)];
}

export interface StepBar {
  step: RunStep;
  /** Milliseconds from the first step's start; null before it has a start time. */
  offsetMs: number | null;
  /** Its duration, or how long it has been running. */
  durationMs: number | null;
  /** Position and width within the whole timeline, in percent (for the bar). */
  left: number;
  width: number;
}

/** The steps laid out on one time axis: where each starts and how long it takes. */
export function stepBars(steps: RunStep[], now: number = Date.now()): StepBar[] {
  const starts = steps.map((s) => ms(s.started_at)).filter((t) => !Number.isNaN(t));
  const origin = starts.length ? Math.min(...starts) : NaN;
  const measured = steps.map((step) => {
    const start = ms(step.started_at);
    const end = step.finished_at ? ms(step.finished_at) : step.status === 'RUNNING' ? now : NaN;
    const duration =
      step.duration_ms !== null && step.duration_ms !== undefined
        ? step.duration_ms
        : Number.isNaN(start) || Number.isNaN(end)
          ? null
          : Math.max(0, end - start);
    return { step, offset: Number.isNaN(start) || Number.isNaN(origin) ? null : start - origin, duration };
  });
  const total = Math.max(1, ...measured.map((m) => (m.offset ?? 0) + (m.duration ?? 0)));
  return measured.map(({ step, offset, duration }) => ({
    step,
    offsetMs: offset,
    durationMs: duration,
    left: offset === null ? 0 : (offset / total) * 100,
    // Never invisible: a step shorter than a pixel still shows as a mark.
    width: Math.max(0.8, duration === null ? 0 : (duration / total) * 100),
  }));
}

export type TruncatedResult = { bytes?: number; preview: string };

/**
 * A result cut for display: the API's ``{truncated: true, bytes, preview}``, or the
 * job host's own marker for a result over what a run record keeps,
 * ``{truncated: true, preview}`` (no byte count).
 */
export function truncatedResult(value: unknown): TruncatedResult | null {
  if (!value || typeof value !== 'object') return null;
  const v = value as Record<string, unknown>;
  if (v.truncated !== true || typeof v.preview !== 'string') return null;
  return typeof v.bytes === 'number' ? { bytes: v.bytes, preview: v.preview } : { preview: v.preview };
}
