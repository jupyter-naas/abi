'use client';

import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import type { PlatformEvent } from '@/app/workspace/[workspaceId]/admin/events/bfo-event-projection';

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
// can grow past it deliberately. With server-side filtering the stream is
// usually quiet, so this rarely bites.
const MAX_EVENTS = 2000;

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
let subscribers = 0;
let pollTimer: ReturnType<typeof setInterval> | null = null;
/** Bumped whenever the stream restarts, so in-flight responses are dropped. */
let generation = 0;
const seenUris = new Set<string>();

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

async function poll(): Promise<void> {
  const state = useEventsStore.getState();
  if (state.authState !== 'authorized') return;
  const gen = generation;
  try {
    const res = await authFetch(buildUrl(state));
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
      return {
        events,
        // Land on the newest row so the graph pane is never empty on arrival.
        selectedUri: prev.selectedUri ?? events[0]?.event._uri ?? null,
      };
    });
  } catch {
    /* non-fatal: the next tick tries again */
  }
}

/** Drop what is loaded and re-read from the top. Used when the filters change. */
function restartStream(): void {
  generation += 1;
  seenUris.clear();
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

  checkAccess: async () => {
    try {
      const res = await authFetch('/api/admin/me');
      if (!res.ok) {
        set({ authState: 'denied' });
        return;
      }
      const data = await res.json();
      set({ authState: data.is_superadmin ? 'authorized' : 'denied' });
    } catch {
      set({ authState: 'denied' });
      return;
    }
    if (get().authState !== 'authorized') return;
    try {
      const res = await authFetch('/api/admin/events/types');
      if (!res.ok) return;
      const data = await res.json();
      set({ availableTypes: Array.isArray(data) ? data : [] });
    } catch {
      /* non-fatal: the dropdown just stays empty */
    }
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
    generation += 1;
    seenUris.clear();
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
      set({ loadingOlder: false });
    }
  },

  subscribe: () => {
    subscribers += 1;
    if (subscribers === 1) {
      void get()
        .checkAccess()
        .then(() => poll());
      pollTimer = setInterval(() => {
        void poll();
      }, EVENTS_POLL_INTERVAL_MS);
    }
    return () => {
      subscribers = Math.max(0, subscribers - 1);
      if (subscribers === 0 && pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };
  },
}));

/** The row the graph pane should draw, or null when nothing is selected. */
export function selectSelectedEvent(state: EventsState): PlatformEvent | null {
  if (!state.selectedUri) return null;
  return state.events.find((row) => row.event._uri === state.selectedUri)?.event ?? null;
}
