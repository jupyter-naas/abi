'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type SetStateAction } from 'react';
import {
  editDraft,
  forgetPageState,
  pageKeyId,
  rebaseDraft,
  usePageStateRegistry,
  writePageState,
  type Draft,
  type DraftRecord,
  type PageKey,
} from '@/lib/page-state';

const sameData = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b);

/**
 * `useState` that a return to the page finds again (`lib/page-state.ts`): filters, sort, the
 * open tab, a selection. Plain data only, never a secret. Back to `initial`, nothing is kept.
 * With a null key (or no known session, or during View as) it is plain component state. When
 * the session changes under an open page, the page starts afresh: it never shows another
 * identity's state.
 */
export function usePageState<T>(key: PageKey | null, initial: T): [T, (next: SetStateAction<T>) => void] {
  const id = key ? pageKeyId(key) : null;
  const owner = usePageStateRegistry((state) => state.owner);
  const initialRef = useRef(initial);
  initialRef.current = initial;
  const restore = (): T => {
    // No session sync here: a render must not update other stores.
    const kept = id !== null ? (usePageStateRegistry.getState().read(id) as T | undefined) : undefined;
    return kept === undefined ? initial : kept;
  };
  const [slot, setSlot] = useState(() => ({ id, owner, value: restore() }));
  let value = slot.value;
  if (slot.id !== id || (slot.owner !== null && slot.owner !== owner)) {
    // Another key, or another session: what it holds (nothing, for a new session).
    value = restore();
    setSlot({ id, owner, value });
  } else if (slot.owner !== owner) {
    // A session became known while the page was open: it adopts what is shown (below).
    setSlot({ ...slot, owner });
  }

  const valueRef = useRef(value);
  valueRef.current = value;
  const keyRef = useRef(key);
  keyRef.current = key;

  const keep = useCallback((next: T) => {
    const pageKey = keyRef.current;
    if (!pageKey) return;
    if (sameData(next, initialRef.current)) forgetPageState(pageKey);
    else writePageState(pageKey, next);
  }, []);

  useEffect(() => {
    if (owner !== null && !sameData(valueRef.current, initialRef.current)) keep(valueRef.current);
  }, [owner, id, keep]);

  const set = useCallback(
    (next: SetStateAction<T>) => {
      const resolved = typeof next === 'function' ? (next as (current: T) => T)(valueRef.current) : next;
      valueRef.current = resolved;
      setSlot((current) => ({ ...current, value: resolved }));
      keep(resolved);
    },
    [keep]
  );

  return [value, set];
}

export interface PageDraft<T extends DraftRecord> {
  /** What the form shows: the server's snapshot under the user's edits; null until it is known. */
  values: T | null;
  /** The fields edited and not saved. */
  dirty: (keyof T & string)[];
  /** Edited fields the server changed since the edit began: the user's value is kept, and shown as such. */
  conflicts: (keyof T & string)[];
  set: (changes: Partial<T>) => void;
  /** Drop the edits (after a save, or to start again from the server). */
  discard: () => void;
}

/**
 * A form's unsaved, non-sensitive edits over a server snapshot. The edits survive leaving and
 * returning (`usePageState`); a fresh snapshot (a background refresh, another read of the
 * resource) updates the fields not edited and never overwrites the edited ones, which it lists
 * as conflicts when it changed them too. Saving stays the page's: it sends `values` (or the
 * changes against its snapshot) as before, then calls `discard`.
 */
export function usePageDraft<T extends DraftRecord>(key: PageKey | null, server: T | null): PageDraft<T> {
  const [draft, setDraft] = usePageState<Draft<T> | null>(key, null);
  const rebased = useMemo(() => (server ? rebaseDraft(draft, server) : null), [draft, server]);

  // Keep the draft rebased on the latest snapshot, so a conflict is counted once and stays.
  useEffect(() => {
    if (rebased && !sameData(rebased.draft, draft)) setDraft(rebased.draft);
  }, [rebased, draft, setDraft]);

  const serverRef = useRef(server);
  serverRef.current = server;
  const set = useCallback(
    (changes: Partial<T>) => {
      const snapshot = serverRef.current;
      if (!snapshot) return;
      setDraft((current) => editDraft(current, snapshot, changes));
    },
    [setDraft]
  );
  const discard = useCallback(() => setDraft(null), [setDraft]);

  return {
    values: rebased?.values ?? null,
    dirty: rebased?.dirty ?? [],
    conflicts: rebased?.conflicts ?? [],
    set,
    discard,
  };
}
