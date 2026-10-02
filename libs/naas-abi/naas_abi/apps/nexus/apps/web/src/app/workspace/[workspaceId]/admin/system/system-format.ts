/** Number, size and time formatting for the System app. */

const BYTE_UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];

function trim(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
}

export function formatBytes(bytes: number): string {
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${trim(unit === 0 ? value : Math.round(value * 10) / 10)} ${BYTE_UNITS[unit]}`;
}

export function formatCount(count: number): string {
  if (count >= 1_000_000) return `${trim(Math.round(count / 100_000) / 10)}M`;
  if (count >= 10_000) return `${trim(Math.round(count / 100) / 10)}k`;
  return String(count);
}

export function formatMs(ms: number): string {
  if (!ms) return '–';
  if (ms >= 1000) return `${trim(Math.round(ms / 100) / 10)} s`;
  return `${Math.round(ms * 100) / 100} ms`;
}

/** ``expiresAt`` and ``now`` in seconds since the epoch. */
export function formatExpiry(expiresAt: number, now: number = Date.now() / 1000): string {
  const left = Math.round(expiresAt - now);
  if (left <= 0) return 'expired';
  const minutes = Math.floor(left / 60);
  const seconds = left % 60;
  return minutes ? `in ${minutes}m ${seconds}s` : `in ${seconds}s`;
}

const SOURCE_LABELS: Record<string, string> = {
  engine: 'Engine',
  nats: 'NATS services',
  discovery: 'Discovery',
  nats_monitor: 'NATS monitoring',
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}
