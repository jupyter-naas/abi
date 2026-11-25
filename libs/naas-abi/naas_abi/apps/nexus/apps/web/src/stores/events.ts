'use client';

import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { fetchPlatformActions } from '@/hooks/use-platform-settings-access';
import { permissionSessionKey, usePermissionCache } from '@/lib/permission-cache';
import type { PlatformEvent } from '@/app/settings/system/events/bfo-event-projection';

export interface EventRow {
  receivedAt: string;
  event: PlatformEvent;
}

export interface EventTypeOption {
  uri: string;
  label: string;
}

export const EVENTS_PAGE_SIZE = 100;
export const EVENTS_POLL_INTERVAL_MS = 5000;

// Soft cap on rows held in memory. The live tail trims to this; "Load older"
// can grow past it deliberately (the next live rows trim it back). With
// server-side filtering the stream is usually quiet, so this rarely bites.
export const MAX_EVENTS = 2000;

export type EventsAuthState = 'checking' | 'authorized' | 'denied';

interface EventsState {
  authState: EventsAuthState;
  events: EventRow[];
  /** `_uri` of the event whose graph the main pane is drawing. */
  selectedUri: string | null;
  paused: boolean;
  classFilter: string;
  search: string;
  availableTypes: EventTypeOption[];
  lastPollAt: number | null;
  loadingOlder: boolean;
  hasMoreOlder: boolean;

  checkAccess: () => Promise<void>;
  setPaused: (paused: boolean) => void;
  setClassFilter: (uri: string) => void;
  setSearch: (query: string) => void;
  selectEvent: (uri: string | null) => void;
  clear: () => void;
  loadOlder: () => Promise<void>;
  /** Join the live tail. Polling runs while at least one caller is subscribed. */
  subscribe: () => () => void;
}

// The feed is shared by the sidebar (which lists it) and the page (which draws
// the selected row), so the tail lives here rather than in either component.
// One read at a time: the next is scheduled once the previous one settles, and
// none is sent while paused, hidden or without a viewer.
let subscribers = 0;
let pollTimer: ReturnType<typeof setTimeout> | null = null;
/** Bumped whenever the stream restarts, so in-flight responses are dropped. */
let generation = 0;
/** The read in flight, for the generation it was begun in. */
let inFlight: { generation: number; controller: AbortController; promise: Promise<void> } | null = null;
/** The `_uri` of every row held, and of no other: bounded by the rows. */
const seenUris = new Set<string>();
let accessCheck: { session: string; promise: Promise<void> } | null = null;

/** How many event ids the tail remembers (tests: it never outgrows the rows held). */
export function seenEventCount(): number {
  return seenUris.size;
}

/** Forget what was loaded and abort the read in flight: its answer would belong to another view. */
function resetStream(): void {
  generation += 1;
  seenUris.clear();
  inFlight?.controller.abort();
  inFlight = null;
}

/** Keep `seenUris` to the rows held once the oldest are trimmed. */
function forgetTrimmed(rows: EventRow[]): void {
  for (const row of rows) seenUris.delete(row.event._uri);
}

function buildUrl(
  state: Pick<EventsState, 'classFilter' | 'search'>,
  beforeSeq?: number | null,
): string {
  const params = new URLSearchParams();
  params.set('limit', String(EVENTS_PAGE_SIZE));
  if (state.classFilter) params.set('event_class', state.classFilter);
  if (state.search) params.set('q', state.search);
  if (beforeSeq != null) params.set('before_seq', String(beforeSeq));
  return `/api/admin/events/recent?${params.toString()}`;
}

/** Server returns oldest-first; present newest-first and drop already-seen. */
function toRows(batch: PlatformEvent[]): EventRow[] {
  const fresh: EventRow[] = [];
  for (const event of [...batch].reverse()) {
    if (seenUris.has(event._uri)) continue;
    seenUris.add(event._uri);
    fresh.push({
      receivedAt: event._stored_at || event.created_at || new Date().toISOString(),
      event,
    });
  }
  return fresh;
}

/** Read the newest events once; a read already in flight for this generation is joined. */
function poll(): Promise<void> {
  const state = useEventsStore.getState();
  // Paused: nothing would be shown, so nothing is read.
  if (state.authState !== 'authorized' || state.paused) return Promise.resolve();
  if (inFlight?.generation === generation) return inFlight.promise;
  const gen = generation;
  const controller = new AbortController();
  const read = async () => {
    try {
      const res = await authFetch(buildUrl(state), { signal: controller.signal });
      if (!res.ok || gen !== generation) return;
      const batch: PlatformEvent[] = await res.json();
      if (gen !== generation) return;
      useEventsStore.setState({ lastPollAt: Date.now() });
      if (useEventsStore.getState().paused) return;
      const fresh = toRows(batch);
      if (fresh.length === 0) return;
      useEventsStore.setState((prev) => {
        const merged = [...fresh, ...prev.events];
        const events = merged.length > MAX_EVENTS ? merged.slice(0, MAX_EVENTS) : merged;
        if (events !== merged) forgetTrimmed(merged.slice(MAX_EVENTS));
        return {
          events,
          // Land on the newest row so the graph pane is never empty on arrival.
          selectedUri: prev.selectedUri ?? events[0]?.event._uri ?? null,
        };
      });
    } catch {
      /* non-fatal (or aborted): the next tick tries again */
    }
  };
  const promise = read().finally(() => {
    if (inFlight?.promise === promise) inFlight = null;
  });
  inFlight = { generation: gen, controller, promise };
  return promise;
}

/** The next read, `EVENTS_POLL_INTERVAL_MS` after the last one settled, while someone watches. */
function schedulePoll(): void {
  if (subscribers === 0 || pollTimer !== null) return;
  pollTimer = setTimeout(() => {
    pollTimer = null;
    if (subscribers === 0) return;
    if (typeof document !== 'undefined' && document.hidden) {
      schedulePoll();
      return;
    }
    void poll().finally(schedulePoll);
  }, EVENTS_POLL_INTERVAL_MS);
}

function stopPolling(): void {
  if (pollTimer !== null) clearTimeout(pollTimer);
  pollTimer = null;
  inFlight?.controller.abort();
  inFlight = null;
}

/** Drop what is loaded and re-read from the top. Used when the filters change. */
function restartStream(): void {
  resetStream();
  useEventsStore.setState({ events: [], hasMoreOlder: true, selectedUri: null });
  void poll();
}

export const useEventsStore = create<EventsState>((set, get) => ({
  authState: 'checking',
  events: [],
  selectedUri: null,
  paused: false,
  classFilter: '',
  search: '',
  availableTypes: [],
  lastPollAt: null,
  loadingOlder: false,
  hasMoreOlder: true,

  checkAccess: () => {
    const session = permissionSessionKey();
    if (accessCheck?.session === session) return accessCheck.promise;
    if (!usePermissionCache.getState().enabled) return Promise.resolve();
    const current = () => permissionSessionKey() === session;
    const read = async () => {
      try {
        // The same ReadSystem decision the Settings navigation already reads.
        const actions = await fetchPlatformActions();
        if (!current()) return;
        set({ authState: actions['nexus:ReadSystem'] === true ? 'authorized' : 'denied' });
      } catch {
        if (current()) set({ authState: 'denied' });
        return;
      }
      if (get().authState !== 'authorized') return;
      try {
        const res = await authFetch('/api/admin/events/types');
        if (!res.ok || !current()) return;
        const data = await res.json();
        if (current()) set({ availableTypes: Array.isArray(data) ? data : [] });
      } catch {
        /* non-fatal: the dropdown just stays empty */
      }
    };
    const promise = read().finally(() => {
      if (accessCheck?.promise === promise) accessCheck = null;
    });
    accessCheck = { session, promise };
    return promise;
  },

  setPaused: (paused) => set({ paused }),

  setClassFilter: (classFilter) => {
    if (get().classFilter === classFilter) return;
    set({ classFilter });
    restartStream();
  },

  setSearch: (search) => {
    if (get().search === search) return;
    set({ search });
    restartStream();
  },

  selectEvent: (selectedUri) => set({ selectedUri }),

  clear: () => {
    resetStream();
    set({ events: [], hasMoreOlder: true, selectedUri: null });
  },

  loadOlder: async () => {
    const state = get();
    if (state.loadingOlder) return;
    let minSeq = Infinity;
    for (const row of state.events) {
      if (typeof row.event._seq === 'number' && row.event._seq < minSeq) {
        minSeq = row.event._seq;
      }
    }
    if (!Number.isFinite(minSeq)) return;
    const gen = generation;
    set({ loadingOlder: true });
    try {
      const res = await authFetch(buildUrl(state, minSeq));
      if (!res.ok || gen !== generation) return;
      const batch: PlatformEvent[] = await res.json();
      if (gen !== generation) return;
      const fresh = toRows(batch);
      set((prev) => ({
        hasMoreOlder: batch.length >= EVENTS_PAGE_SIZE,
        events: fresh.length ? [...prev.events, ...fresh] : prev.events,
      }));
    } catch {
      /* non-fatal */
    } finally {
      if (gen === generation) set({ loadingOlder: false });
    }
  },

  subscribe: () => {
    subscribers += 1;
    if (subscribers === 1) {
      void get()
        .checkAccess()
        .then(() => (subscribers > 0 ? poll() : undefined))
        .finally(schedulePoll);
    }
    let subscribed = true;
    return () => {
      if (!subscribed) return;
      subscribed = false;
      subscribers = Math.max(0, subscribers - 1);
      // Nobody watches: no timer and no read left behind. The rows stay for the return.
      if (subscribers === 0) stopPolling();
    };
  },
}));

usePermissionCache.subscribe((state, previous) => {
  if (state.generation !== previous.generation) {
    resetStream();
    useEventsStore.setState({
      authState: 'checking', events: [], availableTypes: [], selectedUri: null,
      lastPollAt: null, loadingOlder: false, hasMoreOlder: true,
      ...(state.identity !== previous.identity ? { search: '', classFilter: '' } : {}),
    });
  }
  if (state.enabled && subscribers > 0 &&
      (state.generation !== previous.generation || state.revision !== previous.revision)) {
    void useEventsStore.getState().checkAccess().then(() => poll());
  }
});

/** The row the graph pane should draw, or null when nothing is selected. */
export function selectSelectedEvent(state: EventsState): PlatformEvent | null {
  if (!state.selectedUri) return null;
  return state.events.find((row) => row.event._uri === state.selectedUri)?.event ?? null;
}
