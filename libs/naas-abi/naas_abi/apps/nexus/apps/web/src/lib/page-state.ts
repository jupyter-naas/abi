import { create } from 'zustand';
import { synchronizePermissionContext, usePermissionCache } from '@/lib/permission-cache';
import { useResourceCache } from '@/lib/resource-cache';
import { onViewFlagChange, readViewFlag } from '@/lib/view-flag';

/**
 * How a Settings page was left (filters, sort, tabs, selection, scroll, a form's unsaved
 * edits), kept in memory so a return finds it as it was, whatever the page's DOM became
 * meanwhile (a route remount, another level's layout).
 *
 * Entries belong to the session identity the permission cache names (API, user, provider,
 * View as), once the API has confirmed it (the resource cache's session, #1606): a new
 * identity, sign-out, and an unknown session drop them all, and nothing is kept while a
 * view (View as) runs. The session read of a page load confirms a restored user; it is
 * not taken for another identity. Memory only: no persist middleware, no browser storage.
 * Never put a secret, a newly issued key, a payment input or a token here: a page keeps
 * those in its own component state, which goes when it is left.
 */

export const PAGE_STATE_MAX_ENTRIES = 96;
/** One entry, as JSON in UTF-16. */
export const PAGE_STATE_MAX_ENTRY_BYTES = 64 * 1024;
export const PAGE_STATE_MAX_TOTAL_BYTES = 1024 * 1024;

/** Where a state belongs: a scope (`account`, `organization:<id>`, `workspace:<id>`, `platform`), a page, a detail. */
export type PageKey = { scope: string; page: string; detail?: string };

export const pageKeyId = ({ scope, page, detail }: PageKey): string => JSON.stringify([scope, page, detail ?? '']);

type Entry = { value: unknown; bytes: number };

export interface PageStateRegistry {
  /** The session the entries belong to; null keeps nothing. */
  owner: string | null;
  entries: Map<string, Entry>;
  bytes: number;
  bind: (owner: string | null) => void;
  read: (id: string) => unknown;
  /** Keep a value (plain data). False when it is not kept: no owner, not JSON, too large. */
  write: (id: string, value: unknown) => boolean;
  remove: (id: string) => void;
  clear: () => void;
}

export function createPageStateRegistry({
  maxEntries = PAGE_STATE_MAX_ENTRIES,
  maxEntryBytes = PAGE_STATE_MAX_ENTRY_BYTES,
  maxTotalBytes = PAGE_STATE_MAX_TOTAL_BYTES,
}: { maxEntries?: number; maxEntryBytes?: number; maxTotalBytes?: number } = {}) {
  return create<PageStateRegistry>((set, get) => ({
    owner: null,
    entries: new Map(),
    bytes: 0,
    bind: (owner) => {
      if (owner === get().owner) return;
      set({ owner, entries: new Map(), bytes: 0 });
    },
    read: (id) => {
      const entry = get().entries.get(id);
      if (!entry) return undefined;
      // Least recently used goes first: a read counts as a use (no notification needed).
      get().entries.delete(id);
      get().entries.set(id, entry);
      return entry.value;
    },
    write: (id, value) => {
      const state = get();
      let bytes = -1;
      try {
        const text = JSON.stringify(value);
        if (typeof text === 'string') bytes = text.length * 2;
      } catch {
        bytes = -1;
      }
      if (state.owner === null || bytes < 0 || bytes > maxEntryBytes) {
        if (state.entries.has(id)) get().remove(id);
        return false;
      }
      const entries = new Map(state.entries);
      let total = state.bytes - (entries.get(id)?.bytes ?? 0);
      entries.delete(id);
      entries.set(id, { value, bytes });
      total += bytes;
      for (const [oldId, old] of entries) {
        if (entries.size <= maxEntries && total <= maxTotalBytes) break;
        if (oldId === id) continue;
        entries.delete(oldId);
        total -= old.bytes;
      }
      set({ entries, bytes: total });
      return true;
    },
    remove: (id) => {
      const state = get();
      const entry = state.entries.get(id);
      if (!entry) return;
      const entries = new Map(state.entries);
      entries.delete(id);
      set({ entries, bytes: state.bytes - entry.bytes });
    },
    clear: () => set({ entries: new Map(), bytes: 0 }),
  }));
}

export type PageStateStore = ReturnType<typeof createPageStateRegistry>;

export const usePageStateRegistry = createPageStateRegistry();

/** The confirmed session (the resource cache's) when no view runs; else null. */
function followSession(): void {
  const { session } = useResourceCache.getState();
  usePageStateRegistry.getState().bind(session !== null && !readViewFlag() ? session : null);
}
// The resource cache follows the permission cache: listen to both, it settles first.
usePermissionCache.subscribe(followSession);
useResourceCache.subscribe(followSession);
onViewFlagChange(followSession);
followSession();

/** Bring the owner up to date before a read or a write (a session may have changed since). */
function current(): PageStateRegistry {
  synchronizePermissionContext();
  followSession();
  return usePageStateRegistry.getState();
}

export function readPageState<T>(key: PageKey): T | undefined {
  return current().read(pageKeyId(key)) as T | undefined;
}

export function writePageState(key: PageKey, value: unknown): boolean {
  return current().write(pageKeyId(key), value);
}

export function forgetPageState(key: PageKey): void {
  usePageStateRegistry.getState().remove(pageKeyId(key));
}

export function clearPageState(): void {
  usePageStateRegistry.getState().clear();
  followSession();
}

/** Called when the owner changes from a session to another or to none (not at first sign-in). */
export function onPageStateOwnerChange(listener: () => void): () => void {
  return usePageStateRegistry.subscribe((state, previous) => {
    if (previous.owner !== null && state.owner !== previous.owner) listener();
  });
}

/* ----------------------------------------------------------------------------- Drafts */

export type DraftValue = string | number | boolean | null;
export type DraftRecord = Record<string, DraftValue>;

/**
 * A form's unsaved edits. `base` is the server snapshot they were made against; a field is
 * edited (dirty) when its value differs from it. `conflicts` names the edited fields the
 * server changed meanwhile: they stay listed until the edit is saved, discarded or undone.
 */
export type Draft<T extends DraftRecord> = { base: T; values: T; conflicts: (keyof T & string)[] };

export type Rebased<T extends DraftRecord> = {
  /** What to keep: null when nothing is edited. */
  draft: Draft<T> | null;
  values: T;
  dirty: (keyof T & string)[];
  conflicts: (keyof T & string)[];
};

/**
 * Lay a fresh server snapshot under a draft: the fields not edited take the server's
 * value, the edited ones keep the user's, and an edited field the server changed too is a
 * conflict. Pure.
 */
export function rebaseDraft<T extends DraftRecord>(draft: Draft<T> | null, server: T): Rebased<T> {
  if (!draft) return { draft: null, values: server, dirty: [], conflicts: [] };
  const values = { ...server };
  const dirty: (keyof T & string)[] = [];
  const conflicts: (keyof T & string)[] = [];
  for (const field of Object.keys(server) as (keyof T & string)[]) {
    const edited = field in draft.values && !Object.is(draft.values[field], draft.base[field]);
    if (!edited || Object.is(draft.values[field], server[field])) continue;
    values[field] = draft.values[field];
    dirty.push(field);
    if (draft.conflicts.includes(field) || !Object.is(server[field], draft.base[field])) conflicts.push(field);
  }
  if (dirty.length === 0) return { draft: null, values: server, dirty, conflicts };
  return { draft: { base: server, values, conflicts }, values, dirty, conflicts };
}

/** A draft after the user set some fields (against the snapshot it is shown over). */
export function editDraft<T extends DraftRecord>(draft: Draft<T> | null, server: T, changes: Partial<T>): Draft<T> | null {
  const rebased = rebaseDraft(draft, server);
  const values = { ...rebased.values, ...changes };
  const next = rebaseDraft({ base: server, values, conflicts: rebased.conflicts }, server);
  return next.draft;
}
