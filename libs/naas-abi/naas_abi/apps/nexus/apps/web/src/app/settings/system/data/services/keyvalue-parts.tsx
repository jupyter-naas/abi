'use client';

/** Small pieces shared by the key-value and cache views: key families, expiry, value lines. */
import { formatBytes, formatDuration } from '../data-model';
import type { ResourceEntry } from '../data-types';
import { Badge, useNow, type Tone } from '../data-ui';

const PREFIX = /^([A-Za-z0-9_.-]{1,24})[:/]/;

/**
 * ``lock`` for ``lock:object:finance/graph.ttl``, ``signals`` for ``signals/github/last_ingest``;
 * ``null`` when the key has no family.
 */
export function keyPrefix(key: string): string | null {
  return PREFIX.exec(key)?.[1] ?? null;
}

export type KeyFamily = 'lock' | 'session' | 'job' | 'other';

export function keyFamily(key: string): KeyFamily | null {
  const prefix = keyPrefix(key)?.toLowerCase();
  if (!prefix) return null;
  if (/^(lock|locks|mutex|lease)$/.test(prefix)) return 'lock';
  if (/^(session|sessions|auth|token|tokens|otp|magic)$/.test(prefix)) return 'session';
  if (/^(job|jobs|queue|task|tasks|run|runs)$/.test(prefix)) return 'job';
  return 'other';
}

const FAMILY_TONES: Record<KeyFamily, Tone> = {
  lock: 'warn',
  session: 'info',
  job: 'accent',
  other: 'neutral',
};

export function PrefixBadge({ id }: { id: string }) {
  const prefix = keyPrefix(id);
  const family = keyFamily(id);
  if (!prefix || !family) return null;
  return (
    <Badge tone={FAMILY_TONES[family]} mono title={`Key family "${prefix}"`}>
      {prefix}
    </Badge>
  );
}

export interface TtlState {
  tone: Tone;
  label: string;
  seconds: number | null;
}

/** How a key's expiry reads at ``now``: muted without one, amber in its last minute. */
export function ttlState(expiresAt: string | undefined, now: number): TtlState {
  if (!expiresAt) return { tone: 'neutral', label: 'no expiry', seconds: null };
  const at = Date.parse(expiresAt);
  if (Number.isNaN(at)) return { tone: 'neutral', label: 'no expiry', seconds: null };
  const seconds = Math.round((at - now) / 1000);
  if (seconds <= 0) return { tone: 'danger', label: 'expired', seconds: 0 };
  if (seconds < 60) return { tone: 'warn', label: `expires in ${seconds} s`, seconds };
  return { tone: 'info', label: `expires in ${formatDuration(seconds)}`, seconds };
}

/** A live countdown: ticks every second in the last hour, every 30 s before. */
export function TtlBadge({ expiresAt }: { expiresAt?: string }) {
  const soon = expiresAt ? Date.parse(expiresAt) - Date.now() < 3_600_000 : false;
  const now = useNow(soon ? 1000 : 30_000);
  const state = ttlState(expiresAt, now);
  return (
    <span className="data-keyvalue-ttl" title={expiresAt ? new Date(expiresAt).toLocaleString() : undefined}>
      <Badge tone={state.tone}>{state.label}</Badge>
    </span>
  );
}

const ENCODING_LABELS: Record<string, [string, Tone]> = {
  json: ['JSON', 'info'],
  text: ['Text', 'neutral'],
  binary: ['Binary', 'warn'],
};

export function EncodingBadge({ encoding }: { encoding?: string }) {
  if (!encoding) return null;
  const [label, tone] = ENCODING_LABELS[encoding] ?? [encoding, 'neutral'];
  return <Badge tone={tone}>{label}</Badge>;
}

/** The one-line value under a key: the server's snippet, or what kind of bytes it holds. */
export function ValueLine({ entry, opaque }: { entry: ResourceEntry; opaque?: string }) {
  const summary = entry.attributes.summary;
  if (summary) return <span className="data-keyvalue-snippet">{summary}</span>;
  if (opaque) {
    return (
      <span className="data-keyvalue-opaque">
        {opaque}
        {entry.size !== null ? ` · ${formatBytes(entry.size)}` : ''}
      </span>
    );
  }
  return null;
}
