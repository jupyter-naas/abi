import type { AnalyticsGranularity } from './types';

export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatRelative(iso: string, now: number = Date.now()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const diff = Math.max(0, now - t);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

/** A valid IANA timezone, or undefined (the browser's) when the name is unknown here. */
export function safeTimeZone(timeZone: string | null | undefined): string | undefined {
  if (!timeZone) return undefined;
  try {
    new Intl.DateTimeFormat(undefined, { timeZone });
    return timeZone;
  } catch {
    return undefined;
  }
}

/** A timestamp as "Nov 19, 14:05", in the organization's timezone. */
export function formatDateTime(iso: string, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: safeTimeZone(timeZone),
  });
}

/** A timestamp's time of day ("14:05:09"), in the organization's timezone. */
export function formatTime(iso: string, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: safeTimeZone(timeZone),
  });
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

/**
 * A time-series bucket's label. Buckets are already local to the organization's timezone
 * (`YYYY-MM-DDTHH` hourly, `YYYY-MM-DD` daily), so they are read as wall-clock values and
 * never shifted to the browser's timezone. `full` is the tooltip's longer form.
 */
export function formatBucket(bucket: string, granularity: AnalyticsGranularity, full = false): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}))?/.exec(bucket);
  if (!match) return bucket;
  const [, y, mo, d, h] = match;
  const day = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  const hour = h === undefined ? null : Number(h);
  if (granularity === 'hour' && hour !== null) {
    const hh = `${String(hour).padStart(2, '0')}:00`;
    if (!full) return hh;
    return `${day.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })} ${hh}`;
  }
  return day.toLocaleDateString(
    undefined,
    full
      ? { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }
      : { month: 'short', day: 'numeric', timeZone: 'UTC' }
  );
}
