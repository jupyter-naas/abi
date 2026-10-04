/** Pure helpers for the Agents tab. */
import type { Tone } from '../data/data-ui';
import type { AgentRunSummary } from './agents-types';

export const ACTIVE = ['ACCEPTED', 'RUNNING', 'CANCELLING'];
/** What the host still executes: CANCELLING has been asked already. */
export const CANCELLABLE = ['ACCEPTED', 'RUNNING'];

const LABELS: Record<string, string> = {
  ACCEPTED: 'Accepted',
  RUNNING: 'Running',
  CANCELLING: 'Cancelling',
  SUCCEEDED: 'Succeeded',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  TIMED_OUT: 'Timed out',
};

export const STATUS_FILTERS: { id: string; label: string; statuses: string[] }[] = [
  { id: 'all', label: 'All', statuses: [] },
  { id: 'active', label: 'Running', statuses: ACTIVE },
  { id: 'failed', label: 'Failed', statuses: ['FAILED', 'TIMED_OUT'] },
  { id: 'succeeded', label: 'Succeeded', statuses: ['SUCCEEDED'] },
  { id: 'cancelled', label: 'Cancelled', statuses: ['CANCELLED'] },
];

export function statusLabel(status: string): string {
  return LABELS[status] ?? status.charAt(0) + status.slice(1).toLowerCase();
}

export function statusTone(status: string): Tone {
  if (status === 'SUCCEEDED') return 'success';
  if (status === 'RUNNING' || status === 'ACCEPTED') return 'info';
  if (status === 'CANCELLING' || status === 'TIMED_OUT') return 'warn';
  if (status === 'FAILED') return 'danger';
  return 'neutral';
}

export const isActive = (status: string) => ACTIVE.includes(status);
export const isCancellable = (status: string) => CANCELLABLE.includes(status);

/** How long the run took, or has been running for (``now`` for live runs). */
export function runDuration(run: AgentRunSummary, now: number = Date.now()): number | null {
  if (run.duration_ms !== null && run.duration_ms !== undefined) return run.duration_ms;
  const start = run.submitted_at ? Date.parse(run.submitted_at) : NaN;
  if (Number.isNaN(start)) return null;
  const end = run.finished_at ? Date.parse(run.finished_at) : isActive(run.status) ? now : NaN;
  return Number.isNaN(end) ? null : Math.max(0, end - start);
}

/** "service:api" style callers read better without their kind. */
export function callerLabel(caller: string): string {
  return caller || 'unknown';
}

/** ``module/run`` keys split on the first slash (module ids have none). */
export function splitKey(key: string): [string, string] {
  const at = key.indexOf('/');
  return at < 0 ? [key, ''] : [key.slice(0, at), key.slice(at + 1)];
}
