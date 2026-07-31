/**
 * Project EventService LogProcess payloads onto BFO 7 buckets for the
 * Events table. Heuristic only: not full BFO individuals.
 *
 * Column order follows the BFO 7 Buckets book (Material entity → Process →
 * Site → ICE → Quality → Realizable → Temporal region).
 */

export const UNKNOWN = 'Unknown';

export const BFO_COLUMNS = [
  { key: 'materialEntity', label: 'Material entity' },
  { key: 'process', label: 'Process' },
  { key: 'site', label: 'Site' },
  { key: 'ice', label: 'ICE' },
  { key: 'quality', label: 'Quality' },
  { key: 'realizable', label: 'Realizable' },
  { key: 'temporalRegion', label: 'Temporal region' },
] as const;

export type BfoColumnKey = (typeof BFO_COLUMNS)[number]['key'];

export type BfoBuckets = Record<BfoColumnKey, string>;

export interface PlatformEvent {
  _uri: string;
  _class_uri: string;
  _seq: number | null;
  _stored_at: string | null;
  _site?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

function shortClassUri(uri: string): string {
  const slashed = uri.split('/').filter(Boolean).pop() ?? uri;
  return slashed.split('#').pop() ?? slashed;
}

function asNonEmptyString(value: unknown): string | null {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  return null;
}

function firstField(event: PlatformEvent, keys: string[]): string | null {
  for (const key of keys) {
    const value = asNonEmptyString(event[key]);
    if (value) return value;
  }
  return null;
}

function iceRef(event: PlatformEvent): string {
  // Adapter-agnostic ICE pointer into the EventService log (seq is the durable id).
  if (typeof event._seq === 'number') {
    return `event-log#seq=${event._seq}`;
  }
  const uri = asNonEmptyString(event._uri);
  if (uri) return uri;
  return UNKNOWN;
}

function materialEntity(event: PlatformEvent): string {
  return (
    firstField(event, [
      'user_id',
      'userId',
      'agent_name',
      'agentName',
      'actor_id',
      'actorId',
      'participant',
    ]) ?? UNKNOWN
  );
}

function quality(event: PlatformEvent): string {
  const status = firstField(event, ['status', 'state', 'outcome']);
  const latency = firstField(event, [
    'latency',
    'latency_ms',
    'latencyMs',
    'duration',
    'duration_ms',
    'durationMs',
  ]);
  const length = firstField(event, ['content_length', 'contentLength']);

  const parts: string[] = [];
  if (status) parts.push(status);
  if (latency) parts.push(latency.endsWith('ms') ? latency : `${latency}ms`);
  if (length) parts.push(`len=${length}`);
  return parts.length ? parts.join(' · ') : UNKNOWN;
}

function realizable(event: PlatformEvent): string {
  return (
    firstField(event, [
      'tool_name',
      'toolName',
      'role',
      'disposition',
      'function',
      'capability',
    ]) ?? UNKNOWN
  );
}

export function projectEventToBfo(event: PlatformEvent): BfoBuckets {
  const site = firstField(event, ['_site', 'site', 'hostname', 'host']) ?? UNKNOWN;
  const temporal =
    firstField(event, ['created_at', 'createdAt', '_stored_at']) ?? UNKNOWN;

  return {
    materialEntity: materialEntity(event),
    process: shortClassUri(event._class_uri || '') || UNKNOWN,
    site,
    ice: iceRef(event),
    quality: quality(event),
    realizable: realizable(event),
    temporalRegion: temporal,
  };
}
