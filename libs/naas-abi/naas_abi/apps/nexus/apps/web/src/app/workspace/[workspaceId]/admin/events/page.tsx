'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { authFetch } from '@/stores/auth';

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

interface EventType {
  uri: string;
  label: string;
}

// Soft cap on rows held in memory. The live tail trims to this; "Load older"
// can grow past it deliberately. With server-side filtering the stream is
// usually quiet, so this rarely bites.
const MAX_EVENTS = 2000;
const PAGE_SIZE = 100;
const POLL_INTERVAL_MS = 5000;
const SEARCH_DEBOUNCE_MS = 300;

function shortClassUri(uri: string): string {
  const slashed = uri.split('/').filter(Boolean).pop() ?? uri;
  const hashed = slashed.split('#').pop() ?? slashed;
  return hashed;
}

export default function AdminEventsPage() {
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking');
  const [lastPollAt, setLastPollAt] = useState<Date | null>(null);
  const [secondsToNextPoll, setSecondsToNextPoll] = useState<number>(POLL_INTERVAL_MS / 1000);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [paused, setPaused] = useState(false);
  const [classFilter, setClassFilter] = useState<string>('');
  const [searchInput, setSearchInput] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const [availableTypes, setAvailableTypes] = useState<EventType[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(true);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  // Track event URIs already shown so polling / load-older don't duplicate them.
  const seenUrisRef = useRef<Set<string>>(new Set());

  // --- auth gate -----------------------------------------------------------
  useEffect(() => {
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
  }, []);

  // --- debounce the search box into the query-driving `search` -------------
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  // --- load the full event-type registry for the filter dropdown ----------
  // Sourced from the server so EVERY registered type is selectable, not just
  // the ones that happen to be in the current page.
  useEffect(() => {
    if (authState !== 'authorized') return;
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/events/types');
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (!cancelled) setAvailableTypes(Array.isArray(data) ? data : []);
      } catch {
        /* non-fatal: dropdown just stays empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authState]);

  // Build the events query URL for the active filters. `beforeSeq` pages older.
  const buildUrl = useCallback(
    (beforeSeq?: number | null) => {
      const p = new URLSearchParams();
      p.set('limit', String(PAGE_SIZE));
      if (classFilter) p.set('event_class', classFilter);
      if (search) p.set('q', search);
      if (beforeSeq != null) p.set('before_seq', String(beforeSeq));
      return `/api/admin/events/recent?${p.toString()}`;
    },
    [classFilter, search],
  );

  // Server returns oldest-first; present newest-first and drop already-seen.
  const toRows = useCallback((batch: PlatformEvent[]): EventRow[] => {
    const ordered = [...batch].reverse();
    const fresh: EventRow[] = [];
    for (const event of ordered) {
      if (seenUrisRef.current.has(event._uri)) continue;
      seenUrisRef.current.add(event._uri);
      fresh.push({
        receivedAt: event._stored_at || event.created_at || new Date().toISOString(),
        event,
      });
    }
    return fresh;
  }, []);

  // --- live tail; reloads from scratch whenever the filters change --------
  useEffect(() => {
    if (authState !== 'authorized') return;
    let cancelled = false;

    // Filters changed (or first mount) → start a fresh window.
    seenUrisRef.current = new Set();
    setEvents([]);
    setHasMoreOlder(true);

    const poll = async () => {
      try {
        const res = await authFetch(buildUrl());
        if (!res.ok || cancelled) return;
        const batch: PlatformEvent[] = await res.json();
        if (cancelled) return;
        setLastPollAt(new Date());
        setSecondsToNextPoll(POLL_INTERVAL_MS / 1000);
        if (pausedRef.current) return;
        const fresh = toRows(batch);
        if (fresh.length === 0) return;
        setEvents((prev) => {
          const next = [...fresh, ...prev];
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
  }, [authState, buildUrl, toRows]);

  // --- fetch the next older page of matching events -----------------------
  const loadOlder = useCallback(async () => {
    if (loadingOlder) return;
    let minSeq = Infinity;
    for (const r of events) {
      if (typeof r.event._seq === 'number' && r.event._seq < minSeq) {
        minSeq = r.event._seq;
      }
    }
    if (!Number.isFinite(minSeq)) return;
    setLoadingOlder(true);
    try {
      const res = await authFetch(buildUrl(minSeq));
      if (!res.ok) return;
      const batch: PlatformEvent[] = await res.json();
      setHasMoreOlder(batch.length >= PAGE_SIZE);
      const fresh = toRows(batch);
      if (fresh.length) setEvents((prev) => [...prev, ...fresh]);
    } catch {
      /* non-fatal */
    } finally {
      setLoadingOlder(false);
    }
  }, [events, loadingOlder, buildUrl, toRows]);

  const clear = useCallback(() => {
    seenUrisRef.current = new Set();
    setEvents([]);
    setHasMoreOlder(true);
  }, []);

  if (authState === 'checking') {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Checking access…
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <h1 className="text-xl font-semibold">Forbidden</h1>
        <p className="text-sm text-muted-foreground">
          Platform superadmin role required. Set
          <code className="mx-1 rounded bg-muted px-1 py-0.5">is_superadmin: true</code>
          on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.local.yaml</code>
          and restart the API to grant access.
        </p>
      </div>
    );
  }

  const filtering = Boolean(classFilter || search);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="border-b px-6 py-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold">Platform events</h1>
            <p className="text-xs text-muted-foreground">
              {filtering
                ? `Last ${PAGE_SIZE} matching events (server-filtered) · ${events.length} loaded`
                : `Live LogProcess stream from the EventService · ${events.length} loaded`}
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
            title="Filter by event type (server-side: returns the last N of this type)"
          >
            <option value="">All event types ({availableTypes.length})</option>
            {availableTypes.map((t) => (
              <option key={t.uri} value={t.uri}>
                {t.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search payload (whole log)…"
            className="flex-1 min-w-[200px] rounded border px-2 py-1 text-xs"
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-3">
        {events.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            {paused
              ? 'Paused — no new events captured.'
              : filtering
                ? 'No events match the current filters.'
                : 'No events recorded yet. Waiting for live events…'}
          </div>
        ) : (
          <>
            <ul className="space-y-1 font-mono text-xs">
              {events.map((row) => (
                <EventLine key={`${row.receivedAt}-${row.event._uri}`} row={row} />
              ))}
            </ul>
            <div className="py-4 text-center">
              {hasMoreOlder ? (
                <button
                  onClick={loadOlder}
                  disabled={loadingOlder}
                  className="rounded border px-4 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
                >
                  {loadingOlder ? 'Loading…' : 'Load older'}
                </button>
              ) : (
                <span className="text-xs text-muted-foreground">— end of log —</span>
              )}
            </div>
          </>
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
