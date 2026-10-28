/**
 * Feed-card lines for the Events feature-column.
 * Reads the same BFO 7-bucket projection as the center table.
 * Unknown buckets are omitted, not printed.
 */

import {
  UNKNOWN,
  projectEventToBfo,
  type PlatformEvent,
} from './bfo-event-projection';

export type EventKind =
  | 'object'
  | 'agent'
  | 'cache'
  | 'keyvalue'
  | 'email'
  | 'graph'
  | 'secret'
  | 'bus'
  | 'vector'
  | 'error'
  | 'default';

export interface EventFeedItem {
  id: string;
  kind: EventKind;
  className: string;
  /** Actor if known, otherwise Process / event type. */
  line1: string;
  /** Short object id (key, collection, or URI tail). Never Unknown. */
  line2: string;
  /** Site and ICE (or seq). Null when both buckets are empty. */
  line3: string | null;
  /** Quality and Realizable. Null when both are Unknown. */
  line4: string | null;
  occurredAt: string | null;
  timeLabel: string;
}

const SHORT_ID_MAX = 18;

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

export function knownBucket(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === UNKNOWN) return null;
  return trimmed;
}

export function shortClassName(uri: string): string {
  const slashed = uri.split('/').filter(Boolean).pop() ?? uri;
  return slashed.split('#').pop() ?? slashed;
}

/** Last path or fragment segment, trimmed so feed cards do not dump 40-char ids. */
export function shortenFeedId(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return '';
  const last = trimmed.split(/[/#]/).filter(Boolean).pop() ?? trimmed;
  if (last.length <= SHORT_ID_MAX) return last;
  return `${last.slice(0, 10)}...`;
}

function formatIce(ice: string): string {
  const seq = ice.match(/seq=(\d+)/);
  if (seq) return `seq ${seq[1]}`;
  return shortenFeedId(ice);
}

function objectIdOf(event: PlatformEvent): string | null {
  const key = firstField(event, ['key']);
  const prefix = firstField(event, ['prefix']);
  if (key && prefix) {
    return shortenFeedId(`${prefix.replace(/\/+$/, '')}/${key}`);
  }
  if (key) return shortenFeedId(key);
  const named = firstField(event, ['graph_name', 'graphName', 'collection']);
  if (named) return shortenFeedId(named);
  const uri = asNonEmptyString(event._uri);
  return uri ? shortenFeedId(uri) : null;
}

function joinKnown(parts: Array<string | null | undefined>): string | null {
  const cleaned = parts.filter((part): part is string => Boolean(part && part.trim()));
  return cleaned.length ? cleaned.join(' · ') : null;
}

export function formatRelativeTime(iso: string, nowMs: number = Date.now()): string {
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return '';
  const diff = Math.max(0, nowMs - t);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function eventKind(event: PlatformEvent): EventKind {
  const hay = `${event._class_uri} ${shortClassName(event._class_uri)}`.toLowerCase();
  if (hay.includes('error')) return 'error';
  if (hay.includes('agent')) return 'agent';
  if (hay.includes('object')) return 'object';
  if (hay.includes('cache')) return 'cache';
  if (hay.includes('keyvalue') || hay.includes('key_value')) return 'keyvalue';
  if (hay.includes('email')) return 'email';
  if (hay.includes('triple') || hay.includes('graph') || hay.includes('schema')) return 'graph';
  if (hay.includes('secret')) return 'secret';
  if (hay.includes('bus')) return 'bus';
  if (hay.includes('vector') || hay.includes('document') || hay.includes('collection')) {
    return 'vector';
  }
  return 'default';
}

export function projectEventToFeedItem(
  event: PlatformEvent,
  nowMs: number = Date.now(),
): EventFeedItem {
  const buckets = projectEventToBfo(event);
  const process = knownBucket(buckets.process) ?? 'Event';
  const actor = knownBucket(buckets.materialEntity);
  const site = knownBucket(buckets.site);
  const ice = knownBucket(buckets.ice);
  const quality = knownBucket(buckets.quality);
  const realizable = knownBucket(buckets.realizable);

  const line1 = actor ? `${actor} · ${process}` : process;
  const objectId = objectIdOf(event);
  const line2 = objectId ?? process;

  const occurredAt =
    firstField(event, ['created_at', 'createdAt', '_stored_at']) ?? null;

  return {
    id: event._uri,
    kind: eventKind(event),
    className: process,
    line1,
    line2,
    line3: joinKnown([site, ice ? formatIce(ice) : null]),
    line4: joinKnown([quality, realizable]),
    occurredAt,
    timeLabel: occurredAt ? formatRelativeTime(occurredAt, nowMs) : '',
  };
}
