'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, authFetch } from '@/stores/auth';

interface PlatformEvent {
  _uri: string;
  _class_uri: string;
  _seq: number | null;
  _stored_at: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

interface EventRow {
  receivedAt: string;
  event: PlatformEvent;
}

const MAX_EVENTS = 500;
const POLL_INTERVAL_MS = 5000;

function shortClassUri(uri: string): string {
  const slashed = uri.split('/').filter(Boolean).pop() ?? uri;
  const hashed = slashed.split('#').pop() ?? slashed;
  return hashed;
}

export default function AdminEventsPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking');
  const [lastPollAt, setLastPollAt] = useState<Date | null>(null);
  const [secondsToNextPoll, setSecondsToNextPoll] = useState<number>(POLL_INTERVAL_MS / 1000);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [paused, setPaused] = useState(false);
  const [classFilter, setClassFilter] = useState<string>('');
  const [textFilter, setTextFilter] = useState<string>('');
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    if (!user) {
      router.replace('/auth/login');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/me');
        if (!res.ok) {
          if (!cancelled) setAuthState('denied');
          return;
        }
        const data = await res.json();
        if (cancelled) return;
        setAuthState(data.is_superadmin ? 'authorized' : 'denied');
      } catch {
        if (!cancelled) setAuthState('denied');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, router]);

  // Track event URIs we've already shown so polling doesn't duplicate them.
  const seenUrisRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (authState !== 'authorized') return;
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await authFetch('/api/admin/events/recent?limit=100');
        if (!res.ok || cancelled) return;
        const recent: PlatformEvent[] = await res.json();
        if (cancelled) return;
        setLastPollAt(new Date());
        setSecondsToNextPoll(POLL_INTERVAL_MS / 1000);
        if (pausedRef.current) return;
        // Server returns oldest-first; we show newest-first.
        const ordered = [...recent].reverse();
        const newRows: EventRow[] = [];
        for (const event of ordered) {
          if (seenUrisRef.current.has(event._uri)) continue;
          seenUrisRef.current.add(event._uri);
          newRows.push({
            receivedAt: event._stored_at || event.created_at || new Date().toISOString(),
            event,
          });
        }
        if (newRows.length === 0) return;
        setEvents((prev) => {
          const next = [...newRows, ...prev];
          return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next;
        });
      } catch {
        /* non-fatal: next tick will try again */
      }
    };

    poll();
    const pollId = setInterval(poll, POLL_INTERVAL_MS);
    const tickId = setInterval(() => {
      setSecondsToNextPoll((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(pollId);
      clearInterval(tickId);
    };
  }, [authState]);

  const knownClasses = useMemo(() => {
    const set = new Set<string>();
    for (const row of events) set.add(row.event._class_uri);
    return Array.from(set).sort();
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter((row) => {
      if (classFilter && row.event._class_uri !== classFilter) return false;
      if (textFilter) {
        const needle = textFilter.toLowerCase();
        if (!JSON.stringify(row.event).toLowerCase().includes(needle)) return false;
      }
      return true;
    });
  }, [events, classFilter, textFilter]);

  const clear = useCallback(() => setEvents([]), []);

  if (authState === 'checking') {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Checking access…
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 p-8 text-center">
        <h1 className="text-xl font-semibold">Forbidden</h1>
        <p className="text-sm text-muted-foreground">
          Platform superadmin role required. Set
          <code className="mx-1 rounded bg-muted px-1 py-0.5">is_superadmin: true</code>
          on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.yaml</code>
          and restart the API to grant access.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="border-b px-6 py-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold">Platform events</h1>
            <p className="text-xs text-muted-foreground">
              Live LogProcess stream from the EventService. Showing {filtered.length} of{' '}
              {events.length} (max {MAX_EVENTS}).
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                lastPollAt ? 'bg-green-500' : 'bg-zinc-400'
              }`}
            />
            <span className="text-muted-foreground">
              {lastPollAt
                ? `last ${lastPollAt.toLocaleTimeString()} · next in ${secondsToNextPoll}s`
                : 'polling…'}
            </span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={() => setPaused((p) => !p)}
            className="rounded border px-3 py-1 text-xs hover:bg-accent"
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={clear}
            className="rounded border px-3 py-1 text-xs hover:bg-accent"
          >
            Clear
          </button>
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="rounded border px-2 py-1 text-xs"
          >
            <option value="">All event classes</option>
            {knownClasses.map((c) => (
              <option key={c} value={c}>
                {shortClassUri(c)}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={textFilter}
            onChange={(e) => setTextFilter(e.target.value)}
            placeholder="Search payload…"
            className="flex-1 min-w-[200px] rounded border px-2 py-1 text-xs"
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-3">
        {filtered.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            {paused
              ? 'Paused — no new events captured.'
              : events.length === 0
                ? 'No events recorded yet. Waiting for live events…'
                : 'No events match the current filters.'}
          </div>
        ) : (
          <ul className="space-y-1 font-mono text-xs">
            {filtered.map((row) => (
              <EventLine key={`${row.receivedAt}-${row.event._uri}`} row={row} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function EventLine({ row }: { row: EventRow }) {
  const [expanded, setExpanded] = useState(false);
  const ts = row.event.created_at || row.event._stored_at || row.receivedAt;
  const cls = shortClassUri(row.event._class_uri);
  return (
    <li className="rounded border border-transparent hover:border-border">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-3 px-2 py-1 text-left"
      >
        <span className="text-muted-foreground">{ts}</span>
        <span className="rounded bg-muted px-1.5 py-0.5">{cls}</span>
        <span className="truncate text-muted-foreground">{row.event._uri}</span>
      </button>
      {expanded && (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap bg-muted/40 px-3 py-2 text-[11px]">
          {JSON.stringify(row.event, null, 2)}
        </pre>
      )}
    </li>
  );
}
