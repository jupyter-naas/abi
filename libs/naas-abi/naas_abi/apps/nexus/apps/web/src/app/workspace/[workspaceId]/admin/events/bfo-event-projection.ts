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

/** Top-level JSON keys that fill each table column. Same lists as the projection. */
export const BFO_COLUMN_SOURCE_KEYS: Record<BfoColumnKey, readonly string[]> = {
  materialEntity: [
    'user_id',
    'userId',
    'agent_name',
    'agentName',
    'actor_id',
    'actorId',
    'participant',
  ],
  process: ['_class_uri'],
  site: ['_site', 'site', 'hostname', 'host'],
  ice: ['_seq', '_uri'],
  quality: [
    'status',
    'state',
    'outcome',
    'latency',
    'latency_ms',
    'latencyMs',
    'duration',
    'duration_ms',
    'durationMs',
    'content_length',
    'contentLength',
  ],
  realizable: ['tool_name', 'toolName', 'role', 'disposition', 'function', 'capability'],
  temporalRegion: ['created_at', 'createdAt', '_stored_at'],
};

/** bfo-buckets.ts `type` for each Events column (ICE is GDC / information content). */
export const BFO_COLUMN_BUCKET_TYPE: Record<BfoColumnKey, string> = {
  materialEntity: 'Material Entity',
  process: 'Process',
  site: 'Site',
  ice: 'GDC',
  quality: 'Quality',
  realizable: 'Realizable',
  temporalRegion: 'Temporal Region',
};

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

function firstField(event: PlatformEvent, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = asNonEmptyString(event[key]);
    if (value) return value;
  }
  return null;
}

function firstSourceKey(event: PlatformEvent, keys: readonly string[]): string | null {
  for (const key of keys) {
    if (asNonEmptyString(event[key])) return key;
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

const QUALITY_STATUS_KEYS = ['status', 'state', 'outcome'] as const;
const QUALITY_LATENCY_KEYS = [
  'latency',
  'latency_ms',
  'latencyMs',
  'duration',
  'duration_ms',
  'durationMs',
] as const;
const QUALITY_LENGTH_KEYS = ['content_length', 'contentLength'] as const;

function materialEntity(event: PlatformEvent): string {
  return firstField(event, BFO_COLUMN_SOURCE_KEYS.materialEntity) ?? UNKNOWN;
}

function quality(event: PlatformEvent): string {
  const status = firstField(event, QUALITY_STATUS_KEYS);
  const latency = firstField(event, QUALITY_LATENCY_KEYS);
  const length = firstField(event, QUALITY_LENGTH_KEYS);

  const parts: string[] = [];
  if (status) parts.push(status);
  if (latency) parts.push(latency.endsWith('ms') ? latency : `${latency}ms`);
  if (length) parts.push(`len=${length}`);
  return parts.length ? parts.join(' · ') : UNKNOWN;
}

function realizable(event: PlatformEvent): string {
  return firstField(event, BFO_COLUMN_SOURCE_KEYS.realizable) ?? UNKNOWN;
}

export function projectEventToBfo(event: PlatformEvent): BfoBuckets {
  const site = firstField(event, BFO_COLUMN_SOURCE_KEYS.site) ?? UNKNOWN;
  const temporal = firstField(event, BFO_COLUMN_SOURCE_KEYS.temporalRegion) ?? UNKNOWN;

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

/**
 * JSON keys that actually filled each table column for this event.
 * Unknown columns are omitted. No invented values.
 */
export function projectEventToBfoSources(
  event: PlatformEvent,
): Partial<Record<BfoColumnKey, string[]>> {
  const buckets = projectEventToBfo(event);
  const sources: Partial<Record<BfoColumnKey, string[]>> = {};

  const takeFirst = (key: BfoColumnKey) => {
    if (buckets[key] === UNKNOWN) return;
    const field = firstSourceKey(event, BFO_COLUMN_SOURCE_KEYS[key]);
    if (field) sources[key] = [field];
  };

  takeFirst('materialEntity');
  takeFirst('site');
  takeFirst('realizable');
  takeFirst('temporalRegion');

  if (buckets.process !== UNKNOWN) {
    sources.process = ['_class_uri'];
  }

  if (buckets.ice !== UNKNOWN) {
    if (typeof event._seq === 'number') sources.ice = ['_seq'];
    else if (asNonEmptyString(event._uri)) sources.ice = ['_uri'];
  }

  if (buckets.quality !== UNKNOWN) {
    const qualityKeys = [
      firstSourceKey(event, QUALITY_STATUS_KEYS),
      firstSourceKey(event, QUALITY_LATENCY_KEYS),
      firstSourceKey(event, QUALITY_LENGTH_KEYS),
    ].filter((key): key is string => Boolean(key));
    if (qualityKeys.length) sources.quality = qualityKeys;
  }

  return sources;
}
