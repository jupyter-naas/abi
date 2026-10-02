/** Live NATS traffic: SSE frames from the API and what the Traffic tab shows. */

export interface TrafficEvent {
  at: number;
  kind: string;
  subject: string;
  service: string;
  method: string;
  caller: string;
  request_bytes: number;
  reply_bytes: number | null;
  latency_ms: number | null;
  status: 'ok' | 'error' | 'no_reply' | 'published' | string;
  error_code: string;
  trace_id: string;
}

export type TrafficFrame =
  | {
      type: 'status';
      state: 'live' | 'unavailable' | 'ended';
      source?: string | null;
      reason?: string;
      skipped?: Record<string, string>;
    }
  | { type: 'traffic'; events: TrafficEvent[]; dropped: number };

export interface TrafficFilters {
  kind: string; // 'all' or a kind
  text: string;
  errorsOnly: boolean;
}

export interface TrafficSummaryRow {
  key: string;
  kind: string;
  service: string;
  method: string;
  calls: number;
  errors: number;
  averageMs: number;
  bytes: number;
}

/** Complete ``data:`` frames in ``buffer``; ``rest`` is the unfinished tail. */
export function parseSseFrames(buffer: string): { frames: unknown[]; rest: string } {
  const parts = buffer.split('\n\n');
  const rest = parts.pop() ?? '';
  const frames: unknown[] = [];
  for (const part of parts) {
    const data = part
      .split('\n')
      .filter((line) => line.startsWith('data: '))
      .map((line) => line.slice(6))
      .join('\n');
    if (!data) continue;
    try {
      frames.push(JSON.parse(data));
    } catch {
      // Not JSON: ignore the frame.
    }
  }
  return { frames, rest };
}

export function appendTraffic(list: TrafficEvent[], incoming: TrafficEvent[], max = 500): TrafficEvent[] {
  return [...[...incoming].reverse(), ...list].slice(0, max);
}

export function filterTraffic(events: TrafficEvent[], filters: TrafficFilters): TrafficEvent[] {
  const text = filters.text.trim().toLowerCase();
  return events.filter((e) => {
    if (filters.kind !== 'all' && e.kind !== filters.kind) return false;
    if (filters.errorsOnly && e.status !== 'error' && e.status !== 'no_reply') return false;
    if (!text) return true;
    return [e.subject, e.service, e.method, e.caller, e.error_code, e.trace_id].some((v) =>
      v.toLowerCase().includes(text),
    );
  });
}

export function summarizeTraffic(events: TrafficEvent[]): TrafficSummaryRow[] {
  const rows = new Map<string, TrafficSummaryRow & { timed: number; totalMs: number }>();
  for (const e of events) {
    const key = `${e.kind} ${e.service}.${e.method}`;
    const row = rows.get(key) ?? {
      key, kind: e.kind, service: e.service, method: e.method,
      calls: 0, errors: 0, averageMs: 0, bytes: 0, timed: 0, totalMs: 0,
    };
    row.calls += 1;
    if (e.status === 'error' || e.status === 'no_reply') row.errors += 1;
    row.bytes += e.request_bytes + (e.reply_bytes ?? 0);
    if (e.latency_ms !== null) {
      row.timed += 1;
      row.totalMs += e.latency_ms;
    }
    rows.set(key, row);
  }
  return [...rows.values()]
    .map(({ timed, totalMs, ...row }) => ({
      ...row,
      averageMs: timed ? Math.round((totalMs / timed) * 100) / 100 : 0,
    }))
    .sort((a, b) => b.calls - a.calls || a.key.localeCompare(b.key));
}

/** Link to a trace in the configured viewer (Jaeger: ``<ui>/trace/<id>``). */
export function traceLink(uiUrl: string | null | undefined, traceId: string): string | null {
  if (!uiUrl || !traceId) return null;
  return `${uiUrl.replace(/\/+$/, '')}/trace/${traceId}`;
}

const SOURCE_NAMES: Record<string, string> = { traces: 'traces', nats: 'the NATS bus' };

/** Where live traffic comes from: spans (preferred) or the NATS tap (fallback). */
export function liveSourceLabel(source: string | null | undefined, skipped: Record<string, string> | undefined): string {
  if (!source) return 'Live';
  const label = `Live from ${SOURCE_NAMES[source] ?? source}`;
  const why = skipped?.tracing;
  return why ? `${label} (tracing unavailable: ${why})` : label;
}
