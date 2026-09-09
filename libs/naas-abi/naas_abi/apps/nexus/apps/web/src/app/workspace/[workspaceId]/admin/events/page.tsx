'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useEventsStore, selectSelectedEvent } from '@/stores/events';
import {
  UNKNOWN,
  buildEventGraphPayload,
  eventTimestamp,
  formatEventClock,
  formatEventDate,
  summarizeBucket,
} from './bfo-event-projection';
import {
  buildEventGraphModel,
  emptyFilters,
  processLabel,
  type GraphFilters,
} from './event-graph-model';
import {
  DEFAULT_VIEW,
  defaultGraphParams,
  readStoredParams,
  writeStoredParams,
  type GraphParams,
  type GraphView,
} from './event-graph-params';
import { EventGraphCanvas } from './event-graph-canvas';

/**
 * Platform event stream, as BFO-shaped processes.
 *
 * The chronological feed lives in the second sidebar (`EventsSection`); this
 * pane draws the processes it selects, with the Personnel Cockpit's filter and
 * parameter surface over the top. Both read the same store, so the live tail
 * keeps running whether or not the panel is open.
 */
export default function AdminEventsPage() {
  const authState = useEventsStore((s) => s.authState);
  const subscribe = useEventsStore((s) => s.subscribe);
  const selectedEvent = useEventsStore(selectSelectedEvent);
  const selectEvent = useEventsStore((s) => s.selectEvent);
  const rows = useEventsStore((s) => s.events);

  const [params, setParams] = useState<GraphParams>(() => defaultGraphParams(DEFAULT_VIEW));
  const [filters, setFilters] = useState<GraphFilters>(emptyFilters);
  const [search, setSearch] = useState('');
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => subscribe(), [subscribe]);

  // sessionStorage is client-only; hydrate after mount so SSR and the first
  // client render agree.
  useEffect(() => setParams(readStoredParams()), []);

  const updateParams = useCallback((next: GraphParams) => {
    setParams(next);
    writeStoredParams(next);
  }, []);

  const onParamChange = useCallback(
    (key: string, value: string | number | boolean) =>
      updateParams({ ...params, [key]: value } as GraphParams),
    [params, updateParams],
  );

  const onSwitchView = useCallback(
    (view: GraphView) => updateParams({ ...defaultGraphParams(view), processCount: params.processCount }),
    [params.processCount, updateParams],
  );

  const onResetParams = useCallback(
    () => updateParams(defaultGraphParams(params.view)),
    [params.view, updateParams],
  );

  const events = useMemo(() => rows.map((row) => row.event), [rows]);

  const model = useMemo(
    () =>
      buildEventGraphModel(events, filters, {
        focusUri: selectedEvent?._uri ?? null,
        processCount: params.processCount,
      }),
    [events, filters, selectedEvent, params.processCount],
  );

  // Clicking a row in the feed puts that process in the search bar.
  useEffect(() => {
    setSearch(selectedEvent ? processLabel(selectedEvent) : '');
  }, [selectedEvent]);

  const payload = useMemo(
    () => (selectedEvent ? buildEventGraphPayload(selectedEvent) : null),
    [selectedEvent],
  );

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

  if (!selectedEvent || !payload) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <h1 className="text-lg font-semibold">Events</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          {events.length === 0
            ? 'No events recorded yet. Send a chat message or trigger a tool call, and the feed will fill in.'
            : 'Pick a process in the feed to see its BFO 7-bucket graph.'}
        </p>
      </div>
    );
  }

  const at = eventTimestamp(selectedEvent);

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b px-6 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold">
            {payload.naming.verb}
            {payload.naming.object !== UNKNOWN && (
              <span className="font-normal text-muted-foreground"> · {payload.naming.object}</span>
            )}
          </h1>
          <p className="truncate text-xs text-muted-foreground">
            {summarizeBucket(payload, 'Material Entity')}
            {' · '}
            {formatEventDate(at)} {formatEventClock(at)}
            {' · in '}
            {summarizeBucket(payload, 'Site')}
            {' · '}
            <span className="font-mono">{payload.naming.className}</span>
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-muted-foreground">
            {model.nodes.filter((node) => node.isProcess).length} of {model.matchedProcessCount} matching
            processes drawn
          </span>
          {model.focusFiltered && (
            // The focus is drawn regardless, so say why it is there: otherwise
            // it reads as a filter that failed to apply.
            <span className="rounded border border-dashed px-2 py-1 text-muted-foreground">
              selected process is outside the current filters — kept as the focus
            </span>
          )}
          {payload.missing.length > 0 && (
            <span className="text-muted-foreground">
              focus gaps: <span className="font-mono">{payload.missing.join(', ')}</span>
            </span>
          )}
          <button
            onClick={() => setShowRaw((v) => !v)}
            className="rounded border px-2 py-1 hover:bg-accent"
          >
            {showRaw ? 'Hide payload' : 'Raw payload'}
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        <EventGraphCanvas
          model={model}
          params={params}
          filters={filters}
          searchValue={search}
          onParamChange={onParamChange}
          onSwitchView={onSwitchView}
          onResetParams={onResetParams}
          onFiltersChange={setFilters}
          onSearchChange={setSearch}
          onPickProcess={selectEvent}
        />
      </div>

      {showRaw && (
        <pre className="max-h-64 flex-shrink-0 overflow-auto whitespace-pre-wrap border-t px-6 py-3 font-mono text-[11px]">
          {JSON.stringify(selectedEvent, null, 2)}
        </pre>
      )}
    </div>
  );
}
