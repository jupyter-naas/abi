import 'server-only';

import { readDataFile, writeJsonFile } from '@/lib/data/storage';
import type { SessionPayload } from '@/lib/types';

/**
 * Simple, self-hosted usage log — logins and page views. One append-only
 * JSON file, no client-side event SDK, no aggregation pipeline. Page views
 * are captured via PageViewBeacon.tsx (mounted once per shell, fires when
 * the analytics page key or perimeter changes); logins are captured directly
 * in the two auth routes right after the session cookie is set.
 *
 * Page views store a split key:
 *   - page: path without leading slash + filter query
 *     e.g. "contract_management/treasury?scenario=2026"
 *          "contract_management/treasury?scenario=2026&company=11_elzevir"
 *   - perimeter: entity url_slug (e.g. "contract_management"); null for admin
 *
 * Single-file, capped at MAX_EVENTS (oldest trimmed on write). Handful of
 * concurrent users, so the read-modify-write race on concurrent writes is an
 * accepted simplification, not a queue/lock — a rare lost event is fine for
 * internal usage stats.
 */
const EVENTS_KEY = 'globals/analytics_events.json';
const MAX_EVENTS = 5000;

export type AnalyticsEventType = 'login' | 'pageview';

export type AnalyticsEvent = {
  event_id: string;
  type: AnalyticsEventType;
  timestamp: string;
  user_id: string;
  name: string;
  role: 'admin' | 'viewer';
  /**
   * Page URL key (no leading slash), e.g.
   * "contract_management/treasury?scenario=2026&company=11_elzevir".
   * Null for login events.
   */
  page: string | null;
  /** Entity url_slug for portal views; null for admin / login. Absent on legacy events. */
  perimeter?: string | null;
};

type EventsFile = { schema_version: string; records: AnalyticsEvent[] };

const EMPTY_EVENTS_FILE: EventsFile = { schema_version: '1.0', records: [] };

/**
 * Index just past the first complete top-level JSON value in `raw`, or -1.
 * Used to salvage a file whose tail was clobbered by a concurrent write (a
 * valid document followed by leftover bytes); brace/bracket depth is tracked
 * with string contents skipped so braces inside strings don't miscount.
 */
function firstJsonValueEnd(raw: string): number {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === '{' || ch === '[') depth += 1;
    else if (ch === '}' || ch === ']') {
      depth -= 1;
      if (depth === 0) return i + 1;
    }
  }
  return -1;
}

function normalizeEventsFile(parsed: Partial<EventsFile>): EventsFile {
  return {
    schema_version: parsed.schema_version ?? '1.0',
    records: Array.isArray(parsed.records) ? parsed.records : [],
  };
}

function parseEventsFile(raw: string): EventsFile | null {
  try {
    return normalizeEventsFile(JSON.parse(raw) as Partial<EventsFile>);
  } catch {
    // Salvage the valid prefix of a tail-corrupted file (concurrent-write race).
    const end = firstJsonValueEnd(raw);
    if (end > 0) {
      try {
        return normalizeEventsFile(JSON.parse(raw.slice(0, end)) as Partial<EventsFile>);
      } catch {
        /* fall through */
      }
    }
    return null;
  }
}

async function readEventsFile(): Promise<EventsFile> {
  const raw = await readDataFile(EVENTS_KEY);
  if (!raw) {
    return { ...EMPTY_EVENTS_FILE };
  }
  return parseEventsFile(raw) ?? { ...EMPTY_EVENTS_FILE };
}

async function appendEvent(event: AnalyticsEvent): Promise<void> {
  const file = await readEventsFile();
  const records = [...file.records, event].slice(-MAX_EVENTS);
  await writeJsonFile(EVENTS_KEY, { schema_version: '1.0', records });
}

function roleOf(session: SessionPayload): 'admin' | 'viewer' {
  return session.role === 'admin' ? 'admin' : 'viewer';
}

export async function logLogin(session: SessionPayload): Promise<void> {
  try {
    await appendEvent({
      event_id: crypto.randomUUID(),
      type: 'login',
      timestamp: new Date().toISOString(),
      user_id: session.userId,
      name: session.displayName,
      role: roleOf(session),
      page: null,
      perimeter: null,
    });
  } catch {
    // Telemetry is best-effort — never block sign-in on a logging failure.
  }
}

export async function logPageView(
  session: SessionPayload,
  page: string,
  perimeter: string | null,
): Promise<void> {
  try {
    await appendEvent({
      event_id: crypto.randomUUID(),
      type: 'pageview',
      timestamp: new Date().toISOString(),
      user_id: session.userId,
      name: session.displayName,
      role: roleOf(session),
      page,
      perimeter,
    });
  } catch {
    // Best-effort — a dropped page view must never break navigation.
  }
}

export async function loadAnalyticsEvents(): Promise<AnalyticsEvent[]> {
  return (await readEventsFile()).records;
}
