'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Header } from '@/components/shell/header';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { useAdminEventsLog } from './admin-events-log';
import {
  BFO_COLUMNS,
  projectEventToBfo,
  type PlatformEvent,
} from './bfo-event-projection';
import { EventsGraphCanvas } from './events-graph-canvas';
import { eventForGraph } from './events-graph';
import { EventsJsonCanvas } from './events-json-canvas';
import { EventsMenuBar } from './events-menu-bar';

interface EventRow {
  receivedAt: string;
  event: PlatformEvent;
}

// Soft cap on rows held in memory. The live tail trims to this; "Load older"
// can grow past it deliberately. With server-side filtering the stream is
// usually quiet, so this rarely bites.
const MAX_EVENTS = 2000;
const PAGE_SIZE = 100;
const POLL_INTERVAL_MS = 5000;
const SEARCH_DEBOUNCE_MS = 300;

export default function AdminEventsPage() {
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking');
  const [events, setEvents] = useState<EventRow[]>([]);
  const classFilter = useAdminEventsLog((s) => s.classFilter);
  const searchInput = useAdminEventsLog((s) => s.searchInput);
  const search = useAdminEventsLog((s) => s.search);
  const setSearch = useAdminEventsLog((s) => s.setSearch);
  const setAvailableTypes = useAdminEventsLog((s) => s.setAvailableTypes);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMoreOlder, setHasMoreOlder] = useState(true);
  const view = useAdminEventsLog((s) => s.view);
  const setView = useAdminEventsLog((s) => s.setView);
  const projection = useAdminEventsLog((s) => s.projection);

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
  }, [searchInput, setSearch]);

  // --- load the full event-type registry for the filter dropdown ----------
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
  }, [authState, setAvailableTypes]);

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

    seenUrisRef.current = new Set();
    setEvents([]);
    setHasMoreOlder(true);

    const poll = async () => {
      try {
        const res = await authFetch(buildUrl());
        if (!res.ok || cancelled) return;
        const batch: PlatformEvent[] = await res.json();
        if (cancelled) return;
        useAdminEventsLog.getState().setPollStatus(new Date(), POLL_INTERVAL_MS / 1000);
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
      useAdminEventsLog.getState().tickPollCountdown();
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(pollId);
      clearInterval(tickId);
    };
  }, [authState, buildUrl, toRows]);

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

  const selectedUri = useAdminEventsLog((s) => s.selectedUri);
  const setLogEvents = useAdminEventsLog((s) => s.setEvents);
  const graphEvent = useMemo(
    () => eventForGraph(events.map((row) => row.event), selectedUri),
    [events, selectedUri],
  );

  useEffect(() => {
    setLogEvents(events.map((row) => row.event));
  }, [events, setLogEvents]);

  useEffect(() => {
    return () => {
      useAdminEventsLog.getState().clearSession();
    };
  }, []);

  useEffect(() => {
    if (!selectedUri) return;
    const row = document.querySelector(`[data-event-uri="${CSS.escape(selectedUri)}"]`);
    row?.scrollIntoView({ block: 'nearest' });
  }, [selectedUri]);

  const filtering = Boolean(classFilter || search);
  const menuBar = (
    <Header
      title="Events"
      nav={
        <EventsMenuBar
          onLoadOlder={() => void loadOlder()}
          loadOlderDisabled={!hasMoreOlder || events.length === 0}
          loadOlderBusy={loadingOlder}
        />
      }
    />
  );

  if (authState === 'checking') {
    return (
      <div className="flex h-full flex-col">
        {menuBar}
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Checking access…
        </div>
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div className="flex h-full flex-col">
        {menuBar}
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
          <h1 className="text-xl font-semibold">Forbidden</h1>
          <p className="text-sm text-muted-foreground">
            Platform superadmin role required. Set
            <code className="mx-1 rounded bg-muted px-1 py-0.5">is_superadmin: true</code>
            on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.local.yaml</code>
            and restart the API to grant access.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      {menuBar}
      {view === 'graph' ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {events.length === 0 ? (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              {filtering
                ? 'No events match the current filters.'
                : 'No events recorded yet. Waiting for live events…'}
            </div>
          ) : (
            <EventsGraphCanvas
              event={graphEvent}
              projection={projection}
              onViewJson={() => setView('json')}
            />
          )}
        </div>
      ) : view === 'json' ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {events.length === 0 ? (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              {filtering
                ? 'No events match the current filters.'
                : 'No events recorded yet. Waiting for live events…'}
            </div>
          ) : (
            <EventsJsonCanvas event={graphEvent} />
          )}
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-3">
          {events.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {filtering
                ? 'No events match the current filters.'
                : 'No events recorded yet. Waiting for live events…'}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full min-w-[960px]">
                  <thead>
                    <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                      {BFO_COLUMNS.map((col) => (
                        <th
                          key={col.key}
                          className="whitespace-nowrap p-3 font-medium"
                          title={
                            col.key === 'ice'
                              ? 'Information content entity (the stored log record)'
                              : undefined
                          }
                        >
                          {col.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((row) => (
                      <EventTableRow
                        key={`${row.receivedAt}-${row.event._uri}`}
                        row={row}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="py-4 text-center">
                {hasMoreOlder ? (
                  <button
                    type="button"
                    onClick={() => void loadOlder()}
                    disabled={loadingOlder}
                    className="rounded border px-4 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
                  >
                    {loadingOlder ? 'Loading…' : 'Load older'}
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">End of log</span>
                )}
              </div>
              <p className="shrink-0 pb-4 text-xs text-muted-foreground">
                Projection over the EventService log; not full BFO individuals yet.
                Unmapped buckets show <code className="rounded bg-muted px-1 py-0.5">Unknown</code>.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function EventTableRow({ row }: { row: EventRow }) {
  const selectedUri = useAdminEventsLog((s) => s.selectedUri);
  const toggleUri = useAdminEventsLog((s) => s.toggleUri);
  const buckets = projectEventToBfo(row.event);
  const selected = row.event._uri === selectedUri;

  return (
    <>
      <tr
        data-event-uri={row.event._uri}
        aria-selected={selected}
        aria-expanded={selected}
        onClick={() => toggleUri(row.event._uri)}
        className={cn(
          'cursor-pointer border-b font-mono text-[11px] text-foreground transition-colors last:border-0 hover:bg-muted/50',
          selected && 'bg-muted shadow-[inset_2px_0_0_0_hsl(var(--foreground)/0.2)]',
        )}
      >
        {BFO_COLUMNS.map((col) => (
          <td key={col.key} className="max-w-[14rem] truncate p-3 align-top" title={buckets[col.key]}>
            {buckets[col.key]}
          </td>
        ))}
      </tr>
      {selected && (
        <tr className="border-b bg-muted/40 text-foreground">
          <td colSpan={BFO_COLUMNS.length} className="p-0">
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-[11px]">
              {JSON.stringify(row.event, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

