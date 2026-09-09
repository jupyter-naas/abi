'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, Eraser, Pause, Play } from 'lucide-react';
import {
  EVENTS_PAGE_SIZE,
  EVENTS_POLL_INTERVAL_MS,
  useEventsStore,
} from '@/stores/events';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { SidebarToolbar, SidebarToolbarButton } from './sidebar-toolbar';
import { EventFeedItem } from './event-feed-item';
import { getWorkspacePath } from './utils';

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Chronological process feed. One row per event, newest first; selecting a row
 * is what the main pane draws as a BFO graph.
 */
export function EventsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const authState = useEventsStore((s) => s.authState);
  const events = useEventsStore((s) => s.events);
  const selectedUri = useEventsStore((s) => s.selectedUri);
  const paused = useEventsStore((s) => s.paused);
  const classFilter = useEventsStore((s) => s.classFilter);
  const search = useEventsStore((s) => s.search);
  const availableTypes = useEventsStore((s) => s.availableTypes);
  const lastPollAt = useEventsStore((s) => s.lastPollAt);
  const loadingOlder = useEventsStore((s) => s.loadingOlder);
  const hasMoreOlder = useEventsStore((s) => s.hasMoreOlder);
  const subscribe = useEventsStore((s) => s.subscribe);
  const selectEvent = useEventsStore((s) => s.selectEvent);
  const setPaused = useEventsStore((s) => s.setPaused);
  const setClassFilter = useEventsStore((s) => s.setClassFilter);
  const setSearch = useEventsStore((s) => s.setSearch);
  const clear = useEventsStore((s) => s.clear);
  const loadOlder = useEventsStore((s) => s.loadOlder);

  const [searchInput, setSearchInput] = useState(search);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => subscribe(), [subscribe]);

  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput, setSearch]);

  // Drives the "next in Ns" countdown next to the liveness dot.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const secondsToNextPoll = useMemo(() => {
    if (!lastPollAt) return null;
    const elapsed = Math.floor((now - lastPollAt) / 1000);
    return Math.max(0, Math.round(EVENTS_POLL_INTERVAL_MS / 1000) - elapsed);
  }, [lastPollAt, now]);

  const filtering = Boolean(classFilter || search);

  const body = (
    <div className="flex h-full flex-col">
      <SidebarToolbar className="flex-wrap">
        <SidebarToolbarButton
          icon={paused ? <Play size={13} /> : <Pause size={13} />}
          label={paused ? 'Resume the live tail' : 'Pause the live tail'}
          onClick={() => setPaused(!paused)}
          pressed={paused}
        />
        <SidebarToolbarButton
          icon={<Eraser size={13} />}
          label="Clear loaded events"
          onClick={() => clear()}
        />
        <span className="ml-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${lastPollAt ? 'bg-green-500' : 'bg-zinc-400'}`} />
          {lastPollAt ? `next in ${secondsToNextPoll ?? 0}s` : 'polling…'}
        </span>
      </SidebarToolbar>

      <div className="space-y-1 px-1 pb-2">
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="w-full rounded border bg-transparent px-1.5 py-1 text-[11px]"
          title="Filter by event type (server-side: returns the last N of this type)"
        >
          <option value="">All event types ({availableTypes.length})</option>
          {availableTypes.map((type) => (
            <option key={type.uri} value={type.uri}>
              {type.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search payload (whole log)…"
          className="w-full rounded border bg-transparent px-1.5 py-1 text-[11px]"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {authState === 'checking' && (
          <p className="px-2 py-3 text-[11px] text-muted-foreground">Checking access…</p>
        )}
        {authState === 'denied' && (
          <p className="px-2 py-3 text-[11px] text-muted-foreground">
            Platform superadmin role required.
          </p>
        )}
        {authState === 'authorized' && events.length === 0 && (
          <p className="px-2 py-3 text-[11px] text-muted-foreground">
            {paused
              ? 'Paused: no new events captured.'
              : filtering
                ? 'No events match the current filters.'
                : 'No events recorded yet. Waiting for live events…'}
          </p>
        )}
        <div className="space-y-0.5">
          {events.map((row) => (
            <EventFeedItem
              key={row.event._uri}
              row={row}
              active={row.event._uri === selectedUri}
              onSelect={() => selectEvent(row.event._uri)}
            />
          ))}
        </div>
        {events.length > 0 && (
          <div className="px-2 py-3 text-center">
            {hasMoreOlder ? (
              <button
                onClick={() => void loadOlder()}
                disabled={loadingOlder}
                className="rounded border px-3 py-1 text-[10px] hover:bg-accent disabled:opacity-50"
              >
                {loadingOlder ? 'Loading…' : 'Load older'}
              </button>
            ) : (
              <span className="text-[10px] text-muted-foreground">End of log</span>
            )}
          </div>
        )}
        {events.length > 0 && (
          <p className="px-2 pb-3 text-[10px] text-muted-foreground">
            {filtering
              ? `Last ${EVENTS_PAGE_SIZE} matching events (server-filtered) · ${events.length} loaded`
              : `${events.length} loaded`}
          </p>
        )}
      </div>
    </div>
  );

  if (detailOnly) return body;

  return (
    <CollapsibleSection
      id="events"
      icon={<Activity size={18} />}
      label="Events"
      description="Recent platform activity"
      href={getWorkspacePath(currentWorkspaceId, '/admin/events')}
      collapsed={collapsed}
    >
      {body}
    </CollapsibleSection>
  );
}
