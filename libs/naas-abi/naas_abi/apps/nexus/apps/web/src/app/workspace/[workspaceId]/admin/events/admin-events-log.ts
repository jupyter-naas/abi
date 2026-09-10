import { create } from 'zustand';
import type { PlatformEvent } from './bfo-event-projection';

export interface AdminEventType {
  uri: string;
  label: string;
}

export type AdminEventsView = 'table' | 'graph' | 'json';
export type AdminEventsProjection = '2d' | '3d';

const DEFAULT_POLL_COUNTDOWN_S = 5;

/**
 * Shared snapshot of the Events page log so the left Events feed can
 * render the same rows without a second poll. Filter fields and live
 * poll status are the single source of truth for the feed and the
 * table/graph/json query. View and projection are shared by the top-bar
 * menu and the canvas.
 */
interface AdminEventsLogState {
  events: PlatformEvent[];
  selectedUri: string | null;
  classFilter: string;
  searchInput: string;
  search: string;
  availableTypes: AdminEventType[];
  lastPollAt: Date | null;
  secondsToNextPoll: number;
  view: AdminEventsView;
  projection: AdminEventsProjection;
  setEvents: (events: PlatformEvent[]) => void;
  selectUri: (uri: string | null) => void;
  /** Select an event (table expand / JSON view) or clear it if already selected. */
  toggleUri: (uri: string) => void;
  setClassFilter: (uri: string) => void;
  setSearchInput: (value: string) => void;
  setSearch: (value: string) => void;
  setAvailableTypes: (types: AdminEventType[]) => void;
  setPollStatus: (lastPollAt: Date, secondsToNextPoll: number) => void;
  tickPollCountdown: () => void;
  setView: (view: AdminEventsView) => void;
  setProjection: (projection: AdminEventsProjection) => void;
  clearSession: () => void;
}

export const useAdminEventsLog = create<AdminEventsLogState>((set) => ({
  events: [],
  selectedUri: null,
  classFilter: '',
  searchInput: '',
  search: '',
  availableTypes: [],
  lastPollAt: null,
  secondsToNextPoll: DEFAULT_POLL_COUNTDOWN_S,
  view: 'graph',
  projection: '2d',
  setEvents: (events) => set({ events }),
  selectUri: (uri) => set({ selectedUri: uri }),
  toggleUri: (uri) =>
    set((s) => ({ selectedUri: s.selectedUri === uri ? null : uri })),
  setClassFilter: (uri) => set({ classFilter: uri }),
  setSearchInput: (value) => set({ searchInput: value }),
  setSearch: (value) => set({ search: value }),
  setAvailableTypes: (types) => set({ availableTypes: types }),
  setPollStatus: (lastPollAt, secondsToNextPoll) =>
    set({ lastPollAt, secondsToNextPoll }),
  tickPollCountdown: () =>
    set((s) => ({
      secondsToNextPoll: s.secondsToNextPoll > 0 ? s.secondsToNextPoll - 1 : 0,
    })),
  setView: (view) => set({ view }),
  setProjection: (projection) => set({ projection }),
  clearSession: () =>
    set({
      events: [],
      selectedUri: null,
      classFilter: '',
      searchInput: '',
      search: '',
      lastPollAt: null,
      secondsToNextPoll: DEFAULT_POLL_COUNTDOWN_S,
    }),
}));
