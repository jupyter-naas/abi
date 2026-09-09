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

// ---------------------------------------------------------------------------
// Per-event graph projection
//
// The table above answers "what is in this column"; the graph answers "what
// does this one event look like as a shape". Same heuristics, but every bucket
// gets a node — including the ones the payload says nothing about, so the gaps
// in the auto-generated ontologies stay visible instead of silently absent.
// ---------------------------------------------------------------------------

export type BfoBucketType =
  | 'Material Entity'
  | 'Process'
  | 'Temporal Region'
  | 'Site'
  | 'Quality'
  | 'Realizable'
  | 'GDC';

/** Satellite buckets, in the order they are laid out around the process. */
export const EVENT_GRAPH_BUCKETS = [
  'Material Entity',
  'Temporal Region',
  'Site',
  'Quality',
  'Realizable',
  'GDC',
] as const satisfies readonly BfoBucketType[];

/**
 * How the process relates to each satellite, and which way the arrow points.
 * These are the BFO/IAO relations the projection stands in for — the stored
 * payload carries no relation triples of its own.
 */
const BUCKET_RELATIONS: Record<BfoBucketType, { predicate: string; direction: 'out' | 'in' }> = {
  'Material Entity': { predicate: 'has participant', direction: 'out' },
  'Temporal Region': { predicate: 'occupies temporal region', direction: 'out' },
  Site: { predicate: 'occurs in', direction: 'out' },
  Quality: { predicate: 'has quality', direction: 'out' },
  Realizable: { predicate: 'realizes', direction: 'out' },
  GDC: { predicate: 'is about', direction: 'in' },
  Process: { predicate: 'relates to', direction: 'out' },
};

/** More than this in one bucket is noise on a radial layout. */
const MAX_NODES_PER_BUCKET = 4;

export interface EventGraphField {
  /** Payload key the value came from, shown verbatim so gaps are traceable. */
  label: string;
  value: string;
}

export interface EventGraphNode {
  id: string;
  bucket: BfoBucketType;
  label: string;
  /** Payload fields this node was read from. Empty on an Unknown placeholder. */
  fields: EventGraphField[];
  /** false when nothing in the payload populated the bucket. */
  known: boolean;
  /**
   * true when two processes naming the same thing mean the same individual —
   * one user, one host, one tool, one thread. A quality or a log record is
   * borne by its own process and is never merged, even when the label matches.
   */
  shared: boolean;
  predicate: string;
  /** 'out' = process → node, 'in' = node → process. */
  direction: 'out' | 'in';
}

export interface ProcessNaming {
  /** Past-participle verb read off the event class name, upper-cased. */
  verb: string;
  /** What was acted on: a payload field when one names it, else the noun
   *  phrase already present in the class name. */
  object: string;
  className: string;
}

export interface EventGraphPayload {
  process: EventGraphNode;
  /** Satellites, grouped bucket by bucket in EVENT_GRAPH_BUCKETS order. */
  satellites: EventGraphNode[];
  /** Buckets the payload said nothing about; drawn as dashed placeholders. */
  missing: BfoBucketType[];
  naming: ProcessNaming;
}

/** Payload keys that name the thing a process acted on. */
const OBJECT_FIELDS = ['tool_name', 'toolName', 'routed_to', 'routedTo'];

function splitCamelCase(name: string): string[] {
  return name
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .split(/[\s_-]+/)
    .filter(Boolean);
}

/**
 * Read a verb and an object off the event class name.
 *
 * The generated event classes are named `<Subject><Object><VerbPast>`
 * (`AgentToolCalled`), so the trailing word is the only verb the log actually
 * carries. Nothing is inferred beyond splitting a name that is already there;
 * anything the name does not supply stays `Unknown`.
 */
export function deriveProcessNaming(event: PlatformEvent): ProcessNaming {
  const className = shortClassUri(event._class_uri || '');
  const words = splitCamelCase(className);
  const verb = words.length ? words[words.length - 1].toUpperCase() : UNKNOWN;
  const nounWords = words
    .slice(0, -1)
    .filter((word, index) => !(index === 0 && word === 'Agent'));
  const object = firstField(event, OBJECT_FIELDS) ?? (nounWords.join(' ') || UNKNOWN);
  return { verb: verb || UNKNOWN, object, className: className || UNKNOWN };
}

/** The instant the log recorded, preferring the emitter's own clock. */
export function eventTimestamp(event: PlatformEvent): string | null {
  return firstField(event, ['created_at', 'createdAt', '_stored_at']);
}

function parseTimestamp(value: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** `HH:MM:SS` in the reader's timezone, or Unknown when unparseable. */
export function formatEventClock(value: string | null): string {
  const date = parseTimestamp(value);
  if (!date) return UNKNOWN;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

/** `YYYY-MM-DD` in the reader's timezone, or Unknown when unparseable. */
export function formatEventDate(value: string | null): string {
  const date = parseTimestamp(value);
  if (!date) return UNKNOWN;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function excerpt(value: string, max = 120): string {
  const flat = value.replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

export function buildEventGraphPayload(event: PlatformEvent): EventGraphPayload {
  const naming = deriveProcessNaming(event);
  let counter = 0;

  const make = (
    bucket: BfoBucketType,
    label: string,
    fields: EventGraphField[],
    known = true,
    shared = false,
  ): EventGraphNode => {
    counter += 1;
    const relation = BUCKET_RELATIONS[bucket];
    return {
      id: `n${counter}`,
      bucket,
      label,
      fields,
      known,
      shared,
      predicate: relation.predicate,
      direction: relation.direction,
    };
  };

  const field = (label: string, value: string): EventGraphField[] => [{ label, value }];

  // --- Material entity: who took part ------------------------------------
  const material: EventGraphNode[] = [];
  const user = firstField(event, ['user_id', 'userId', 'actor_id', 'actorId']);
  if (user) material.push(make('Material Entity', user, field('user_id', user), true, true));
  const agent = firstField(event, ['agent_name', 'agentName']);
  if (agent) material.push(make('Material Entity', agent, field('agent_name', agent), true, true));
  const routedTo = firstField(event, ['routed_to', 'routedTo']);
  if (routedTo) material.push(make('Material Entity', routedTo, field('routed_to', routedTo), true, true));

  // --- Temporal region: when ---------------------------------------------
  // Storage is point-in-time, so a range only appears when the payload happens
  // to carry both ends.
  const temporal: EventGraphNode[] = [];
  const from = firstField(event, ['from', 'started_at', 'startedAt']);
  const to = firstField(event, ['to', 'ended_at', 'endedAt']);
  const at = eventTimestamp(event);
  if (from && to) {
    temporal.push(
      make('Temporal Region', `${formatEventClock(from)} → ${formatEventClock(to)}`, [
        { label: 'from', value: from },
        { label: 'to', value: to },
      ]),
    );
  } else if (at) {
    const sourceKey = firstField(event, ['created_at', 'createdAt']) ? 'created_at' : '_stored_at';
    temporal.push(
      make('Temporal Region', `${formatEventDate(at)} ${formatEventClock(at)}`, field(sourceKey, at), true, true),
    );
  }

  // --- Site: where --------------------------------------------------------
  const site: EventGraphNode[] = [];
  const host = firstField(event, ['_site', 'site', 'hostname', 'host']);
  if (host) site.push(make('Site', host, field('_site', host), true, true));
  const workspace = firstField(event, ['workspace_id', 'workspaceId']);
  if (workspace) site.push(make('Site', workspace, field('workspace_id', workspace), true, true));

  // --- Quality: how it went ----------------------------------------------
  const qualities: EventGraphNode[] = [];
  const status = firstField(event, ['status', 'state', 'outcome']);
  if (status) qualities.push(make('Quality', status, field('status', status)));
  const latency = firstField(event, [
    'latency_ms', 'latencyMs', 'latency', 'duration_ms', 'durationMs', 'duration',
  ]);
  if (latency) {
    const shown = latency.endsWith('ms') ? latency : `${latency}ms`;
    qualities.push(make('Quality', shown, field('latency', latency)));
  }
  const length = firstField(event, ['content_length', 'contentLength']);
  if (length) qualities.push(make('Quality', `len=${length}`, field('content_length', length)));

  // --- Realizable: the capability the process realized ---------------------
  const realizables: EventGraphNode[] = [];
  const tool = firstField(event, ['tool_name', 'toolName']);
  if (tool) realizables.push(make('Realizable', tool, field('tool_name', tool), true, true));
  const role = firstField(event, ['role', 'disposition', 'function', 'capability']);
  if (role) realizables.push(make('Realizable', role, field('role', role), true, true));

  // --- GDC: the evidence the record leaves behind -------------------------
  // The stored log record is itself the ICE about this process, so this bucket
  // is always populated by at least one node.
  const gdc: EventGraphNode[] = [make('GDC', iceRef(event), field('_uri', event._uri))];
  const content = firstField(event, ['content']);
  if (content) gdc.push(make('GDC', 'content', field('content', excerpt(content))));
  const toolArgs = firstField(event, ['tool_args', 'toolArgs']);
  if (toolArgs) gdc.push(make('GDC', 'tool_args', field('tool_args', excerpt(toolArgs))));
  const chat = firstField(event, ['chat_id', 'chatId']);
  if (chat) gdc.push(make('GDC', chat, field('chat_id', chat), true, true));

  const byBucket: Record<string, EventGraphNode[]> = {
    'Material Entity': material,
    'Temporal Region': temporal,
    Site: site,
    Quality: qualities,
    Realizable: realizables,
    GDC: gdc,
  };

  const satellites: EventGraphNode[] = [];
  const missing: BfoBucketType[] = [];
  for (const bucket of EVENT_GRAPH_BUCKETS) {
    const found = byBucket[bucket].slice(0, MAX_NODES_PER_BUCKET);
    if (found.length === 0) {
      missing.push(bucket);
      satellites.push(make(bucket, UNKNOWN, [], false));
      continue;
    }
    satellites.push(...found);
  }

  counter += 1;
  const process: EventGraphNode = {
    id: `n${counter}`,
    bucket: 'Process',
    label: naming.object === UNKNOWN ? naming.verb : `${naming.verb} ${naming.object}`,
    fields: [
      { label: '_class_uri', value: event._class_uri || UNKNOWN },
      { label: '_seq', value: event._seq == null ? UNKNOWN : String(event._seq) },
    ],
    known: naming.className !== UNKNOWN,
    shared: false,
    predicate: BUCKET_RELATIONS.Process.predicate,
    direction: 'out',
  };

  return { process, satellites, missing, naming };
}

/** Every label a bucket contributed, or Unknown when it contributed none. */
export function summarizeBucket(payload: EventGraphPayload, bucket: BfoBucketType): string {
  const labels = payload.satellites
    .filter((node) => node.bucket === bucket && node.known)
    .map((node) => node.label);
  return labels.length ? labels.join(' · ') : UNKNOWN;
}

/** `{Material entity} · {verb} · {object}` — the feed row's subtitle. */
export function eventSentence(payload: EventGraphPayload): string {
  const who = summarizeBucket(payload, 'Material Entity').split(' · ')[0];
  return [who, payload.naming.verb, payload.naming.object].join(' · ');
}
